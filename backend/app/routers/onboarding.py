from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.chunking import chunk_text
from app.db import get_db
from app.embeddings import embed_many
from app.models import ProfileChunk, User
from app.parsing import extract_text
from app.questions import ONBOARDING_QUESTIONS
from app.schemas import AnswerIn, AnswersIn, OnboardingStatus

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/questions")
async def get_questions() -> list[str]:
    return ONBOARDING_QUESTIONS


@router.get("/status", response_model=OnboardingStatus)
async def get_status(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    qa_count = await db.scalar(
        select(func.count()).select_from(ProfileChunk).where(
            ProfileChunk.user_id == current_user.id, ProfileChunk.source == "qa"
        )
    )
    preview = None
    if current_user.resume_raw_text:
        preview = current_user.resume_raw_text[:200].strip()
        if len(current_user.resume_raw_text) > 200:
            preview += "…"

    return OnboardingStatus(
        onboarding_completed=current_user.onboarding_completed,
        resume_uploaded=current_user.resume_raw_text is not None,
        resume_preview=preview,
        answers_count=qa_count or 0,
        questions_total=len(ONBOARDING_QUESTIONS),
    )


async def _store_resume_text(db: AsyncSession, user: User, text: str) -> int:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Resume text is empty")

    user.resume_raw_text = text
    # Replace, don't append — re-uploading a resume should mirror overwriting resume_raw_text,
    # not pile up duplicate chunks that crowd out real content in top-k retrieval later.
    await db.execute(delete(ProfileChunk).where(ProfileChunk.user_id == user.id, ProfileChunk.source == "resume"))
    chunks = chunk_text(text)
    vectors = embed_many(chunks)
    for content, vector in zip(chunks, vectors):
        db.add(ProfileChunk(user_id=user.id, source="resume", content=content, embedding=vector))
    await db.commit()
    return len(chunks)


@router.post("/resume")
async def upload_resume(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file is not None:
        data = await file.read()
        extracted = extract_text(file.filename or "", data)
    elif text:
        extracted = text
    else:
        raise HTTPException(status_code=400, detail="Provide either a file upload or pasted text")

    chunk_count = await _store_resume_text(db, current_user, extracted)
    return {"chunks_created": chunk_count, "preview": extracted[:500]}


def _parse_qa_chunk(content: str) -> tuple[str, str] | None:
    if not content.startswith("Q: ") or "\nA: " not in content:
        return None
    question, answer = content[3:].split("\nA: ", 1)
    return question, answer


@router.get("/answers", response_model=list[AnswerIn])
async def get_answers(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProfileChunk).where(ProfileChunk.user_id == current_user.id, ProfileChunk.source == "qa")
    )
    answers = []
    for chunk in result.scalars().all():
        parsed = _parse_qa_chunk(chunk.content)
        if parsed:
            answers.append(AnswerIn(question=parsed[0], answer=parsed[1]))
    return answers


@router.post("/answers")
async def submit_answers(
    payload: AnswersIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.answers:
        raise HTTPException(status_code=400, detail="No answers provided")

    to_save = [a for a in payload.answers if a.answer.strip()]

    # Replace, don't append — resubmitting an already-answered question (now routine, since the
    # UI pre-fills existing answers for editing) would otherwise pile up duplicate chunks for the
    # same question, same class of bug as the earlier resume-upload duplication issue.
    existing_result = await db.execute(
        select(ProfileChunk).where(ProfileChunk.user_id == current_user.id, ProfileChunk.source == "qa")
    )
    existing_chunks = list(existing_result.scalars().all())
    questions_being_saved = {a.question for a in to_save}
    for chunk in existing_chunks:
        parsed = _parse_qa_chunk(chunk.content)
        if parsed and parsed[0] in questions_being_saved:
            await db.delete(chunk)

    combined = [f"Q: {a.question}\nA: {a.answer}" for a in to_save]
    vectors = embed_many(combined)
    for content, vector in zip(combined, vectors):
        db.add(ProfileChunk(user_id=current_user.id, source="qa", content=content, embedding=vector))

    current_user.onboarding_completed = current_user.resume_raw_text is not None
    await db.commit()
    return {"answers_stored": len(combined), "onboarding_completed": current_user.onboarding_completed}
