from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis import run_ats_semantic_analysis
from app.auth import get_current_user
from app.chunking import chunk_text
from app.db import get_db
from app.embeddings import embed, embed_many
from app.models import Analysis, CoverLetter, GeneratedResume, Job, JobChunk, User
from app.schemas import AnalysisOut, ConfirmedSkillIn, JobIn, JobOut, StatusUpdate
from app.search import top_profile_chunks

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

VALID_STATUSES = {"progress", "sent", "interview", "offer", "rejected"}


async def _get_owned_job(db: AsyncSession, job_id: int, user_id: int) -> Job:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=AnalysisOut)
async def create_job(
    payload: JobIn, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    text = payload.raw_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Job posting text is empty")

    job = Job(user_id=current_user.id, raw_text=text, title=payload.title, company=payload.company)
    db.add(job)
    await db.flush()

    chunks = chunk_text(text)
    vectors = embed_many(chunks)
    for content, vector in zip(chunks, vectors):
        db.add(JobChunk(job_id=job.id, content=content, embedding=vector))

    query_embedding = embed(text)
    relevant_chunks = await top_profile_chunks(db, current_user.id, query_embedding, k=8)
    if not relevant_chunks:
        raise HTTPException(status_code=400, detail="No profile data yet — complete onboarding first")

    result = run_ats_semantic_analysis(text, relevant_chunks)

    analysis = Analysis(
        job_id=job.id,
        items=result.get("items", []),
        confidence_score=int(result.get("confidence_score", 0)),
        summary=result.get("summary", ""),
    )
    db.add(analysis)
    await db.commit()
    await db.refresh(analysis)

    return AnalysisOut(
        id=analysis.id,
        job_id=job.id,
        items=analysis.items,
        confidence_score=analysis.confidence_score,
        summary=analysis.summary,
        created_at=analysis.created_at,
    )


@router.get("", response_model=list[JobOut])
async def list_jobs(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Job).where(Job.user_id == current_user.id).order_by(Job.updated_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{job_id}")
async def get_job(
    job_id: int, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    job = await _get_owned_job(db, job_id, current_user.id)

    analysis_result = await db.execute(
        select(Analysis).where(Analysis.job_id == job_id).order_by(Analysis.created_at.desc()).limit(1)
    )
    analysis = analysis_result.scalar_one_or_none()

    resumes_result = await db.execute(
        select(GeneratedResume).where(GeneratedResume.job_id == job_id).order_by(GeneratedResume.created_at.desc())
    )
    resumes = list(resumes_result.scalars().all())

    letters_result = await db.execute(
        select(CoverLetter).where(CoverLetter.job_id == job_id).order_by(CoverLetter.created_at.desc())
    )
    letters = list(letters_result.scalars().all())

    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "status": job.status,
        "raw_text": job.raw_text,
        "created_at": job.created_at,
        "confirmed_skills": job.confirmed_skills,
        "analysis": None
        if analysis is None
        else {
            "items": analysis.items,
            "confidence_score": analysis.confidence_score,
            "summary": analysis.summary,
        },
        "resumes": [
            {
                "id": r.id,
                "content": r.content,
                "changes": r.changes,
                "version": r.version,
                "match_score": r.match_score,
                "match_summary": r.match_summary,
                "created_at": r.created_at,
            }
            for r in resumes
        ],
        "cover_letters": [{"id": c.id, "content": c.content, "created_at": c.created_at} for c in letters],
    }


@router.patch("/{job_id}/status", response_model=JobOut)
async def update_status(
    job_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(VALID_STATUSES)}")

    job = await _get_owned_job(db, job_id, current_user.id)
    job.status = payload.status
    await db.commit()
    await db.refresh(job)
    return job


@router.patch("/{job_id}/confirmed-skills")
async def set_confirmed_skill(
    job_id: int,
    payload: ConfirmedSkillIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_owned_job(db, job_id, current_user.id)

    skills = set(job.confirmed_skills)
    if payload.has_it:
        skills.add(payload.skill)
    else:
        skills.discard(payload.skill)
    job.confirmed_skills = sorted(skills)

    await db.commit()
    return {"confirmed_skills": job.confirmed_skills}
