import uuid
from datetime import datetime

from pydantic import BaseModel


class SourceResponse(BaseModel):
    domain: str
    name: str
    type: str
    country: str | None
    score: float
    cases_count: int
    low_sample: bool


class SourceScoreEventResponse(BaseModel):
    claim_id: uuid.UUID
    outcome: str
    created_at: datetime


class SourceDetailResponse(SourceResponse):
    score_interval_low: float
    score_interval_high: float
    recent_events: list[SourceScoreEventResponse]


class SourceListResponse(BaseModel):
    sources: list[SourceResponse]
