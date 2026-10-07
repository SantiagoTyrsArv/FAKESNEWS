import uuid
from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user, require_csrf
from app.core.rate_limit import get_redis_dependency
from app.modules.auth.models import User
from app.modules.submissions import service
from app.modules.submissions.schemas import (
    CreateSubmissionRequest,
    SubmissionListResponse,
    SubmissionResponse,
)

router = APIRouter(prefix="/submissions", tags=["submissions"])


def _to_response(submission) -> SubmissionResponse:
    return SubmissionResponse(
        id=submission.id,
        input_type=submission.input_type,
        raw_input=submission.raw_input,
        status=submission.status,
        error=submission.error,
        created_at=submission.created_at,
    )


@router.post("", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    body: CreateSubmissionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
    user: Annotated[User, Depends(get_current_user)],
    _csrf: Annotated[None, Depends(require_csrf)],
):
    try:
        submission = await service.create_submission(
            db,
            redis_client,
            user_id=user.id,
            input_type=body.input_type,
            raw_input=body.raw_input,
        )
    except service.InputTypeDisabledError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "El análisis de video no está disponible por ahora. Envía el texto o un enlace.",
        ) from exc
    except service.SubmissionQuotaError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            exc.message,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    return _to_response(submission)


@router.get("", response_model=SubmissionListResponse)
async def list_submissions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    submissions = await service.list_submissions(db, user_id=user.id)
    return SubmissionListResponse(submissions=[_to_response(s) for s in submissions])


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    try:
        submission = await service.get_submission(db, submission_id=submission_id, user_id=user.id)
    except service.SubmissionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Caso no encontrado.") from exc
    return _to_response(submission)
