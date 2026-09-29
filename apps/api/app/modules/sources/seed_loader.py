import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.sources.models import Source

settings = get_settings()
logger = get_logger(__name__)


async def load_trusted_sources(db: AsyncSession, path: str | None = None) -> int:
    """Idempotently upsert app/data/trusted_sources.json into the sources
    table. Existing domains are left untouched (their alpha/beta scores may
    have moved since the seed priors). Returns the number of new rows added.
    """
    resolved_path = Path(path or settings.trusted_sources_path)
    entries = json.loads(resolved_path.read_text(encoding="utf-8"))

    result = await db.execute(select(Source.domain))
    existing_domains = set(result.scalars().all())

    added = 0
    for entry in entries:
        if entry["domain"] in existing_domains:
            continue
        db.add(
            Source(
                domain=entry["domain"],
                name=entry["name"],
                type=entry["type"],
                country=entry.get("country"),
                syndication_group=entry.get("syndication_group"),
                alpha=float(entry.get("prior_alpha", 1)),
                beta=float(entry.get("prior_beta", 1)),
                cases_count=0,
            )
        )
        added += 1

    if added:
        await db.commit()
        logger.info("trusted_sources_seeded", added=added)

    return added
