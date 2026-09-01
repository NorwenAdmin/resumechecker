from app.sectioning import section_document


def chunk_document(text: str, doc_type: str = "document") -> list[dict]:
    """Section-aware chunking: never packs content across a section boundary into one chunk.
    Returns [{"content": str, "section": str, "core_requirement": bool}, ...]."""
    sections = section_document(text, doc_type)
    chunks = []
    for sec in sections:
        for piece in chunk_text(sec["content"]):
            chunks.append(
                {"content": piece, "section": sec["label"], "core_requirement": sec["core_requirement"]}
            )
    return chunks


def chunk_text(text: str, target_size: int = 600, overlap: int = 80) -> list[str]:
    """Split text into paragraph-aware chunks of roughly target_size chars with overlap."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 1 > target_size:
            chunks.append(current.strip())
            current = current[-overlap:] + "\n" + para
        else:
            current = f"{current}\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks
