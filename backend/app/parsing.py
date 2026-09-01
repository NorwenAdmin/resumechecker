import io

from fastapi import HTTPException


def extract_text(filename: str, data: bytes) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _extract_pdf(data)
    elif lower.endswith(".docx"):
        text = _extract_docx(data)
    else:
        raise HTTPException(status_code=400, detail="Only PDF or DOCX files are supported")

    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Couldn't find any text in that file — if it's a scanned/image PDF with no "
            "text layer, paste the resume text instead.",
        )
    return text


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Couldn't read this PDF: {exc}") from exc


def _extract_docx(data: bytes) -> str:
    from docx import Document

    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Couldn't read this DOCX file: {exc}") from exc
