from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.modules.sources import reputation, service
from app.modules.sources.models import Source
from app.modules.sources.schemas import (
    SourceDetailResponse,
    SourceListResponse,
    SourceResponse,
    SourceScoreEventResponse,
)

router = APIRouter(prefix="/sources", tags=["sources"])


def _to_response(source: Source) -> SourceResponse:
    return SourceResponse(
        domain=source.domain,
        name=source.name,
        type=source.type,
        country=source.country,
        score=reputation.compute_score(source),
        cases_count=source.cases_count,
        low_sample=reputation.is_low_sample(source),
    )


@router.get("", response_model=SourceListResponse)
async def list_sources(db: Annotated[AsyncSession, Depends(get_db)]):
    sources = await service.list_sources(db)
    return SourceListResponse(sources=[_to_response(s) for s in sources])


@router.get("/{domain}", response_model=SourceDetailResponse)
async def get_source(domain: str, db: Annotated[AsyncSession, Depends(get_db)]):
    source = await service.get_source_by_domain(db, domain)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuente no encontrada.")

    low, high = reputation.compute_score_interval(source)
    events = await service.list_recent_events(db, source.id)

    base = _to_response(source)
    return SourceDetailResponse(
        **base.model_dump(),
        score_interval_low=low,
        score_interval_high=high,
        recent_events=[
            SourceScoreEventResponse(
                claim_id=e.claim_id, outcome=e.outcome, created_at=e.created_at
            )
            for e in events
        ],
    )
