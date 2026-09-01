from app.claude_client import complete, complete_json
from app.models import ProfileChunk, User

STYLE_GUIDE = (
    "Direct, concise, first-person, no corporate fluff or buzzwords. Evolution not revolution. "
    "Sounds like a person, not a corporate document. Never invents facts, tools, or numbers that "
    "aren't in the provided excerpts. When a tool/package's real name uses snake_case or another "
    "code-style identifier (e.g. integration_test), don't drop it mid-sentence in prose — keep the "
    "real name but phrase around it naturally (e.g. \"Flutter's integration_test package\") or place "
    "it in a skills/tools list instead, so it doesn't read like a stray code token in a sentence."
)


def voice_guide(user: User) -> str:
    role = f", {user.title}" if user.title else ""
    return f"{user.name}{role}. {STYLE_GUIDE}"


def resume_system(user: User) -> str:
    return (
        "You are a resume writer working strictly from a candidate's real background. "
        f"Voice: {voice_guide(user)} Respond with strict JSON only, no prose outside JSON."
    )


RESUME_JSON_SHAPE = """{
  "resume_markdown": "the full adapted resume in markdown",
  "changes": [{"section": "e.g. Summary", "before": "original phrasing or empty string if new", "after": "new phrasing", "reason": "why this change helps for this job"}]
}"""


def _confirmed_skills_block(confirmed_skills: list[str]) -> str:
    if not confirmed_skills:
        return ""
    skills = ", ".join(confirmed_skills)
    return (
        f"\n\nCONFIRMED ADDITIONAL SKILLS (the candidate explicitly confirmed direct experience with "
        f"these — they weren't in the resume or Q&A above, but the candidate told us directly they have "
        f"them): {skills}\nYou may mention these (e.g. in a skills list) since the candidate is the "
        f"source, but do NOT invent a project, story, or metric around them — none was given, only the "
        f"skill name itself."
    )


def build_resume_prompt(
    job_text: str, resume_raw_text: str, qa_chunks: list[ProfileChunk], confirmed_skills: list[str] | None = None
) -> str:
    stories = "\n\n".join(c.content for c in qa_chunks)
    stories_block = (
        f"\n\nADDITIONAL Q&A ANSWERS (real stories/context — optional texture, not a substitute for "
        f"anything in the resume above):\n{stories}"
        if stories
        else ""
    )
    return f"""JOB POSTING:
{job_text}

CANDIDATE'S FULL CURRENT RESUME (the complete, real record — every role and entry here is real and
must still be present in your output; you may reword, reorder, and re-emphasize for this posting,
but never drop or shorten away a real role/entry):
{resume_raw_text}{stories_block}{_confirmed_skills_block(confirmed_skills or [])}

TASK:
Adapt the candidate's resume for this specific job posting, in the candidate's voice. Keep the full
work history — reorder and re-emphasize what's most relevant to this posting, tighten wording, but
every role/entry present in the resume above must still appear in your output. Do not fabricate
tools, metrics, or experience not present above. List every meaningful change you made and why, so
the candidate can review each decision.

Respond with JSON matching exactly this shape:
{RESUME_JSON_SHAPE}"""


def generate_resume(
    user: User,
    job_text: str,
    resume_raw_text: str,
    qa_chunks: list[ProfileChunk],
    confirmed_skills: list[str] | None = None,
) -> dict:
    prompt = build_resume_prompt(job_text, resume_raw_text, qa_chunks, confirmed_skills)
    return complete_json(resume_system(user), prompt, max_tokens=8192)


def cover_letter_system(user: User) -> str:
    return (
        "You write short, direct cover letters strictly from a candidate's real background. "
        f"Voice: {voice_guide(user)} "
        "Critical constraint: the job posting below will list tools, languages, and requirements the "
        "candidate does NOT have. Do not mirror that language back as if the candidate has it. Only "
        "claim a skill, tool, or language if it appears verbatim (or as a listed equivalent) in the "
        "resume or profile excerpts — never because the job posting asked for it. If a requirement isn't "
        "covered, either omit it or address the adjacent skill that IS real, but never claim the gap away. "
        "Respond with plain text only — the cover letter itself, nothing else."
    )


def build_cover_letter_prompt(
    job_text: str, resume_markdown: str, chunks: list[ProfileChunk], confirmed_skills: list[str] | None = None
) -> str:
    excerpts = "\n\n".join(f"[{c.source}] {c.content}" for c in chunks)
    return f"""JOB POSTING (source of requirements only — do NOT restate its keywords as candidate claims):
{job_text}

CANDIDATE'S ADAPTED RESUME FOR THIS JOB (ground every claim in this or the excerpts below):
{resume_markdown}

ADDITIONAL PROFILE EXCERPTS (real stories/context, use for texture, not filler):
{excerpts}{_confirmed_skills_block(confirmed_skills or [])}

TASK:
Write a short cover letter (under 250 words) in the candidate's voice. Lead with a real, specific
story or result from the excerpts that's relevant to this job, not generic claims. Before writing
each sentence that names a tool, language, or skill, check it appears in the resume or excerpts above
— if it doesn't, don't write it, even if the job posting asked for it. No corporate boilerplate.
Plain text output only."""


def generate_cover_letter(
    user: User,
    job_text: str,
    resume_markdown: str,
    chunks: list[ProfileChunk],
    confirmed_skills: list[str] | None = None,
) -> str:
    prompt = build_cover_letter_prompt(job_text, resume_markdown, chunks, confirmed_skills)
    return complete(cover_letter_system(user), prompt, max_tokens=1000)
