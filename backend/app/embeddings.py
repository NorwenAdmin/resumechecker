from functools import lru_cache


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def embed(text: str) -> list[float]:
    return _model().encode(text, normalize_embeddings=True).tolist()


def embed_many(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _model().encode(texts, normalize_embeddings=True).tolist()
