from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import score_resume_match
from app.auth import get_current_user
from app.chunking import chunk_document
from app.db import get_db
from app.embeddings import embed, embed_many
from app.generation import generate_cover_letter, generate_resume
from app.models import CoverLetter, GeneratedResume, Job, JobChunk, ProfileChunk, User
from app.pdf_export import DEFAULT_TEMPLATE, generate_resume_pdf
from app.schemas import CoverLetterOut, PromoteToProfileIn, ResumeEditIn, ResumeOut
from app.search import top_profile_chunks

router = APIRouter(prefix="/api/jobs", tags=["generate"])


async def _get_owned_job(db: AsyncSession, job_id: int, user_id: int) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


async def _build_job_query_text(db: AsyncSession, job: Job) -> str:
    """Prefer the already-sectioned core-requirement chunks from create_job (no duplicate Claude
    call) over the raw posting text, which usually also carries marketing/culture noise. Falls
    back to the full raw text for jobs created before section-aware chunking existed."""
    result = await db.execute(select(JobChunk).where(JobChunk.job_id == job.id))
    chunks = list(result.scalars().all())
    core_content = [c.content for c in chunks if c.metadata_.get("core_requirement")]
    return "\n\n".join(core_content) if core_content else job.raw_text


@router.post("/{job_id}/resume", response_model=ResumeOut)
async def create_resume(
    job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    job = await _get_owned_job(db, job_id, current_user.id)

    if not current_user.resume_raw_text:
        raise HTTPException(status_code=400, detail="No profile data yet — complete onboarding first")

    query_text = await _build_job_query_text(db, job)
    query_embedding = embed(query_text)
    qa_chunks = await top_profile_chunks(db, current_user.id, query_embedding, k=6, source="qa")

    result = generate_resume(current_user, job.raw_text, current_user.resume_raw_text, qa_chunks, job.confirmed_skills)
    resume_markdown = result.get("resume_markdown", "")

    score_result = score_resume_match(job.raw_text, resume_markdown)

    existing_count_result = await db.execute(select(GeneratedResume).where(GeneratedResume.job_id == job_id))
    version = len(list(existing_count_result.scalars().all())) + 1

    resume = GeneratedResume(
        job_id=job_id,
        content=resume_markdown,
        changes=result.get("changes", []),
        version=version,
        match_score=score_result.get("match_score"),
        match_summary=score_result.get("summary"),
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return ResumeOut(
        id=resume.id,
        job_id=job_id,
        content=resume.content,
        changes=resume.changes,
        version=resume.version,
        match_score=resume.match_score,
        match_summary=resume.match_summary,
    )


@router.post("/{job_id}/cover-letter", response_model=CoverLetterOut)
async def create_cover_letter(
    job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    job = await _get_owned_job(db, job_id, current_user.id)

    latest_resume_result = await db.execute(
        select(GeneratedResume).where(GeneratedResume.job_id == job_id).order_by(GeneratedResume.created_at.desc()).limit(1)
    )
    latest_resume = latest_resume_result.scalar_one_or_none()
    resume_text = latest_resume.content if latest_resume else ""

    query_text = await _build_job_query_text(db, job)
    query_embedding = embed(query_text)
    qa_chunks = await top_profile_chunks(db, current_user.id, query_embedding, k=6, source="qa")

    content = generate_cover_letter(current_user, job.raw_text, resume_text, qa_chunks, job.confirmed_skills)

    letter = CoverLetter(job_id=job_id, content=content)
    db.add(letter)
    await db.commit()
    await db.refresh(letter)
    return CoverLetterOut(id=letter.id, job_id=job_id, content=letter.content)


@router.patch("/{job_id}/resume/{resume_id}", response_model=ResumeOut)
async def edit_resume(
    job_id: int,
    resume_id: int,
    payload: ResumeEditIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_job(db, job_id, current_user.id)

    resume = await db.get(GeneratedResume, resume_id)
    if resume is None or resume.job_id != job_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    resume.content = payload.content
    await db.commit()
    await db.refresh(resume)
    return ResumeOut(
        id=resume.id,
        job_id=job_id,
        content=resume.content,
        changes=resume.changes,
        version=resume.version,
        match_score=resume.match_score,
        match_summary=resume.match_summary,
    )


@router.get("/{job_id}/resume/{resume_id}/pdf")
async def download_resume_pdf(
    job_id: int,
    resume_id: int,
    template: str = DEFAULT_TEMPLATE,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_owned_job(db, job_id, current_user.id)

    resume = await db.get(GeneratedResume, resume_id)
    if resume is None or resume.job_id != job_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    pdf_bytes = generate_resume_pdf(resume.content, template)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="resume.pdf"'},
    )


@router.post("/{job_id}/resume/{resume_id}/promote-to-profile")
async def promote_to_profile(
    job_id: int,
    resume_id: int,
    payload: PromoteToProfileIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.promote:
        return {"promoted": False}

    await _get_owned_job(db, job_id, current_user.id)

    resume = await db.get(GeneratedResume, resume_id)
    if resume is None or resume.job_id != job_id:
        raise HTTPException(status_code=404, detail="Resume not found")

    # This becomes the new base resume — replace resume_raw_text and its chunks, don't just add
    # to them, so the base profile stays a single source of truth instead of an accumulating log.
    current_user.resume_raw_text = resume.content
    await db.execute(
        delete(ProfileChunk).where(ProfileChunk.user_id == current_user.id, ProfileChunk.source == "resume")
    )
    chunks = chunk_document(resume.content, "resume")
    vectors = embed_many([c["content"] for c in chunks])
    for chunk, vector in zip(chunks, vectors):
        db.add(
            ProfileChunk(
                user_id=current_user.id,
                source="resume",
                content=chunk["content"],
                embedding=vector,
                metadata_={"promoted_from_job_id": job_id, "section": chunk["section"]},
            )
        )
    await db.commit()
    return {"promoted": True, "chunks_added": len(chunks)}
