import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.submissions.schemas import InputType, SubmissionStatus


class ReportSource(BaseModel):
    domain: str
    name: str
    type: str
    score: float
    cases_count: int
    low_sample: bool


class ReportEvidence(BaseModel):
    url: str
    snippet: str
    published_at: str | None
    stance: str
    source: ReportSource


class ReportClaim(BaseModel):
    id: uuid.UUID
    text: str
    verdict: str
    rationale: str
    confidence_note: str | None
    evidence: list[ReportEvidence]


class ReportSubmission(BaseModel):
    id: uuid.UUID
    input_type: InputType
    raw_input: str
    status: SubmissionStatus
    created_at: datetime


class ReportSummary(BaseModel):
    total_claims: int
    supported: int
    contradicted: int
    insufficient: int


class ReportResponse(BaseModel):
    submission: ReportSubmission
    summary: ReportSummary
    claims: list[ReportClaim]
    disclaimer: str
