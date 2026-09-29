import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import Source, SourceScoreEvent


def normalize_domain(url_or_domain: str) -> str:
    """Extract a bare, lowercased, www-stripped domain from a URL or a
    domain string, so it can be matched against `sources.domain`.
    """
    value = url_or_domain.strip().lower()
    value = urlparse(value).netloc if "//" in value else value.split("/", 1)[0]
    value = value.split(":", 1)[0]
    if value.startswith("www."):
        value = value[len("www.") :]
    return value


async def get_source_by_domain(db: AsyncSession, domain: str) -> Source | None:
    normalized = normalize_domain(domain)
    result = await db.execute(select(Source).where(Source.domain == normalized))
    return result.scalar_one_or_none()


async def get_allowed_domains(db: AsyncSession) -> list[str]:
    result = await db.execute(select(Source.domain))
    return list(result.scalars().all())


async def list_sources(db: AsyncSession) -> list[Source]:
    result = await db.execute(select(Source).order_by(Source.name))
    return list(result.scalars().all())


async def list_recent_events(
    db: AsyncSession, source_id: uuid.UUID, limit: int = 20
) -> list[SourceScoreEvent]:
    result = await db.execute(
        select(SourceScoreEvent)
        .where(SourceScoreEvent.source_id == source_id)
        .order_by(SourceScoreEvent.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
