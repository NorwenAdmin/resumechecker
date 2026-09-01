"""Splits a document (resume or job posting) into labeled sections, so chunking never merges
unrelated content (e.g. the tail of "Experience" with the start of "Skills") into one chunk.

Two paths, deliberately different:
- Markdown (our own AI-generated resumes, `## Heading` style): parsed deterministically with a
  regex. The format is one we control completely, so there's no ambiguity to resolve — no reason
  to spend an API call guessing something that's already known.
- Raw/unstructured text (uploaded PDF/DOCX resumes, pasted job postings): real-world documents use
  too many different section-naming conventions and layouts for a fixed keyword list to ever fully
  cover — regex heuristics here are a losing, endlessly-patched game. A single Claude call finds
  section boundaries instead. Critically, the model is asked only to report where each section
  *starts* (a short exact quote), never to reproduce or summarize the content — the actual text is
  sliced out of the original by Python, so the source text can never be paraphrased or dropped.
"""

import re

from app.claude_client import complete_json

_MARKDOWN_HEADER_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)


def _split_by_markdown_headers(text: str) -> list[dict]:
    matches = list(_MARKDOWN_HEADER_RE.finditer(text))
    if not matches:
        return [{"label": "Document", "content": text, "core_requirement": True}]

    sections = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append({"label": "Header", "content": preamble, "core_requirement": True})

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections.append({"label": m.group(1).strip(), "content": content, "core_requirement": True})

    return sections


BOUNDARY_SYSTEM = (
    "You identify section boundaries in unstructured documents (resumes or job postings). You do "
    "not rewrite, summarize, paraphrase, or drop any text — you only report where each section "
    "starts, quoting the opening words exactly as they appear character-for-character. Respond "
    "with strict JSON only, no prose outside JSON."
)

BOUNDARY_JSON_SHAPE = """{
  "sections": [
    {
      "label": "short section name, e.g. Experience, Skills, Education, Requirements, Responsibilities, Benefits, About",
      "starts_with": "the first 5-10 words of this section, copied character-for-character from the document",
      "core_requirement": true or false
    }
  ]
}"""


def _split_with_ai(text: str, doc_type: str) -> list[dict]:
    prompt = f"""Identify the natural sections of this {doc_type} and exactly where each one starts.

For each section, also judge core_requirement: true for sections about skills, experience,
responsibilities, or requirements (the substance a candidate/screener would match against) — false
for sections that are marketing/culture/logistics (About us, Benefits, Perks, How to apply, Why join
us, company description).

DOCUMENT:
{text}

Respond with JSON matching exactly this shape:
{BOUNDARY_JSON_SHAPE}"""

    result = complete_json(BOUNDARY_SYSTEM, prompt, max_tokens=2048)

    boundaries = []
    for item in result.get("sections", []):
        marker = (item.get("starts_with") or "").strip()
        if not marker:
            continue
        pos = text.find(marker)
        if pos >= 0:
            boundaries.append((pos, item.get("label", "Section"), bool(item.get("core_requirement", True))))

    if not boundaries:
        return [{"label": "Document", "content": text, "core_requirement": True}]

    boundaries.sort(key=lambda b: b[0])

    sections = []
    if boundaries[0][0] > 0:
        preamble = text[: boundaries[0][0]].strip()
        if preamble:
            sections.append({"label": "Header", "content": preamble, "core_requirement": True})

    for i, (pos, label, core) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        content = text[pos:end].strip()
        if content:
            sections.append({"label": label, "content": content, "core_requirement": core})

    return sections


def section_document(text: str, doc_type: str = "document") -> list[dict]:
    """Returns [{"label": str, "content": str, "core_requirement": bool}, ...] covering the full
    text with no gaps or overlaps between sections."""
    if _MARKDOWN_HEADER_RE.search(text):
        return _split_by_markdown_headers(text)
    return _split_with_ai(text, doc_type)
