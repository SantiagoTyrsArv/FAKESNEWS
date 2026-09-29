import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

InputType = Literal["text", "url", "video"]
SubmissionStatus = Literal[
    "queued",
    "ingesting",
    "transcribing",
    "extracting",
    "verifying",
    "scoring",
    "done",
    "failed",
]


class CreateSubmissionRequest(BaseModel):
    input_type: InputType
    raw_input: str = Field(min_length=1, max_length=10000)


class SubmissionResponse(BaseModel):
    id: uuid.UUID
    input_type: InputType
    raw_input: str
    status: SubmissionStatus
    error: str | None
    created_at: datetime


class SubmissionListResponse(BaseModel):
    submissions: list[SubmissionResponse]
