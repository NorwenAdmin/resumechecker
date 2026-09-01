from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    title: str | None
    onboarding_completed: bool

    class Config:
        from_attributes = True


class OnboardingStatus(BaseModel):
    onboarding_completed: bool
    resume_uploaded: bool
    resume_preview: str | None = None
    answers_count: int
    questions_total: int


class AnswerIn(BaseModel):
    question: str
    answer: str


class AnswersIn(BaseModel):
    answers: list[AnswerIn]


class JobIn(BaseModel):
    raw_text: str
    title: str | None = None
    company: str | None = None


class JobOut(BaseModel):
    id: int
    title: str | None
    company: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class GapItem(BaseModel):
    requirement: str
    ats_missing: bool
    ats_note: str
    real_gap: bool
    semantic_note: str


class AnalysisOut(BaseModel):
    id: int
    job_id: int
    items: list[GapItem]
    confidence_score: int
    summary: str
    confirmed_skills: list[str] = []
    created_at: datetime


class ChangeItem(BaseModel):
    section: str
    before: str
    after: str
    reason: str


class ResumeOut(BaseModel):
    id: int
    job_id: int
    content: str
    changes: list[ChangeItem]
    version: int
    match_score: int | None = None
    match_summary: str | None = None


class CoverLetterOut(BaseModel):
    id: int
    job_id: int
    content: str


class StatusUpdate(BaseModel):
    status: str


class ResumeEditIn(BaseModel):
    content: str


class PromoteToProfileIn(BaseModel):
    promote: bool


class ConfirmedSkillIn(BaseModel):
    skill: str
    has_it: bool
