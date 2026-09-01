from app.claude_client import complete_json
from app.equivalence import as_prompt_block
from app.models import ProfileChunk

SYSTEM = (
    "You are a blunt, precise recruiting-technology assistant. You compare a job description "
    "against a candidate's real background (given as retrieved resume/profile excerpts) and, for "
    "each distinct requirement in the posting, judge two separate things: whether the exact wording "
    "appears in the resume (an ATS keyword scanner only matches literal text) and whether the "
    "candidate genuinely has the underlying skill (a semantic judgment that accounts for equivalent "
    "tools/wording). Never invent skills or experience the candidate doesn't have. Respond with "
    "strict JSON only, no prose outside JSON."
)

JSON_SHAPE = """{
  "items": [
    {
      "requirement": "the skill, tool, title phrase, or requirement as stated in the job posting",
      "ats_missing": true or false,
      "ats_note": "why it's missing / what exact wording to add — empty string if ats_missing is false",
      "real_gap": true or false,
      "semantic_note": "explanation of whether the candidate genuinely has this or it's just wording"
    }
  ],
  "confidence_score": 0-100,
  "summary": "1-3 sentence blunt verdict on whether to apply"
}"""


def build_prompt(job_text: str, chunks: list[ProfileChunk]) -> str:
    excerpts = "\n\n".join(f"[{c.source}] {c.content}" for c in chunks)
    return f"""JOB POSTING:
{job_text}

CANDIDATE PROFILE EXCERPTS (most relevant, retrieved via semantic search):
{excerpts}

KNOWN SKILL EQUIVALENCE GROUPS (treat these as interchangeable, not gaps, when comparing):
{as_prompt_block()}

TASK:
Go through the job posting and extract every distinct requirement — skills, tools, titles, years of
experience, anything a screener would check for. For EACH requirement, produce ONE item with both
judgments:

1. ats_missing: does the exact phrase from the posting literally appear anywhere in the candidate's
   excerpts? A naive ATS keyword scanner only matches literal text, so mark true even when an
   equivalent skill exists under different wording. If true, ats_note says what exact wording to add.
2. real_gap: does the candidate genuinely lack this skill/experience, accounting for equivalents (the
   equivalence groups above, or any other clearly-equivalent tool/wording present in the excerpts)?
   Only mark true when there is no real equivalent — a pure wording difference is real_gap: false even
   if ats_missing is true for the same item. semantic_note explains the judgment either way.

A requirement that's just a title or years-of-experience phrasing (not a discrete skill) can still get
both fields — real_gap is usually false for those unless the candidate's actual experience falls short.

Also give a confidence_score (0-100) for whether the candidate should apply as-is, and a short, direct
summary — no corporate fluff.

Respond with JSON matching exactly this shape:
{JSON_SHAPE}"""


def run_ats_semantic_analysis(job_text: str, chunks: list[ProfileChunk]) -> dict:
    prompt = build_prompt(job_text, chunks)
    return complete_json(SYSTEM, prompt, max_tokens=8192)


MATCH_SCORE_SYSTEM = (
    "You are a blunt, precise recruiting-technology assistant. You score how well a specific "
    "resume matches a specific job posting — this resume has already been tailored for this job, "
    "so judge the result, not the candidate's raw background. Respond with strict JSON only, no "
    "prose outside JSON."
)

MATCH_SCORE_SHAPE = """{
  "match_score": 0-100,
  "summary": "1-2 sentence blunt verdict on how well this tailored resume matches this posting"
}"""


def build_match_score_prompt(job_text: str, resume_markdown: str) -> str:
    return f"""JOB POSTING:
{job_text}

TAILORED RESUME (already adapted for this posting):
{resume_markdown}

TASK:
Score how well this specific resume matches this specific job posting, as an ATS + human screener
would read it — exact keyword coverage and genuine skill match both count. This is the tailored
result, not raw background, so judge what's actually on the page.

Respond with JSON matching exactly this shape:
{MATCH_SCORE_SHAPE}"""


def score_resume_match(job_text: str, resume_markdown: str) -> dict:
    prompt = build_match_score_prompt(job_text, resume_markdown)
    return complete_json(MATCH_SCORE_SYSTEM, prompt, max_tokens=1500)
