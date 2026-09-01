import io
import re

import markdown
from fastapi import HTTPException
from xhtml2pdf import pisa

_LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+\.)\s")


def _ensure_blank_line_before_lists(text: str) -> str:
    """Python-Markdown (unlike CommonMark) only starts a list after a blank line — a list
    directly following a paragraph line gets swallowed into that paragraph instead of
    rendering as list items. Insert the blank line deterministically rather than relying on
    the model to always leave one."""
    lines = text.split("\n")
    result: list[str] = []
    for i, line in enumerate(lines):
        is_list_item = bool(_LIST_ITEM_RE.match(line))
        prev_line = result[-1] if result else ""
        prev_is_list_item = bool(_LIST_ITEM_RE.match(prev_line))
        if is_list_item and prev_line.strip() and not prev_is_list_item:
            result.append("")
        result.append(line)
    return "\n".join(result)

# Each template is just CSS. Add more entries here later (e.g. "compact", "two-column")
# without touching the rendering logic below.
TEMPLATES: dict[str, str] = {
    "classic": """
        @page { size: A4; margin: 2cm; }
        body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.4; }
        h1 { font-size: 20pt; margin: 0 0 4pt; }
        h2 { font-size: 12pt; border-bottom: 1px solid #333; padding-bottom: 3pt; margin-top: 16pt; margin-bottom: 6pt; }
        h3 { font-size: 11pt; margin-bottom: 2pt; }
        p { margin: 4pt 0; }
        ul { margin: 4pt 0; padding-left: 16pt; }
        li { margin-bottom: 3pt; }
        strong { font-weight: bold; }
        hr { border: none; border-top: 1px solid #ccc; margin: 10pt 0; }
    """,
}

DEFAULT_TEMPLATE = "classic"


def generate_resume_pdf(resume_markdown: str, template: str = DEFAULT_TEMPLATE) -> bytes:
    css = TEMPLATES.get(template)
    if css is None:
        raise HTTPException(status_code=400, detail=f"Unknown template '{template}'. Available: {list(TEMPLATES)}")

    normalized = _ensure_blank_line_before_lists(resume_markdown)
    body_html = markdown.markdown(normalized, extensions=["extra"])
    html = f"<html><head><style>{css}</style></head><body>{body_html}</body></html>"

    buffer = io.BytesIO()
    result = pisa.CreatePDF(html, dest=buffer)
    if result.err:
        raise HTTPException(status_code=500, detail="Failed to render PDF")
    return buffer.getvalue()
