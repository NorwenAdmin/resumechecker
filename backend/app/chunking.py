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
