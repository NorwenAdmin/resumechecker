from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ProfileChunk


async def top_profile_chunks(
    db: AsyncSession, user_id: int, query_embedding: list[float], k: int = 8, source: str | None = None
) -> list[ProfileChunk]:
    stmt = select(ProfileChunk).where(ProfileChunk.user_id == user_id)
    if source is not None:
        stmt = stmt.where(ProfileChunk.source == source)
    stmt = stmt.order_by(ProfileChunk.embedding.cosine_distance(query_embedding)).limit(k)
    result = await db.execute(stmt)
    return list(result.scalars().all())
