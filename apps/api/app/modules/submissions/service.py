import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.queue import enqueue
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.modules.submissions.models import Submission

settings = get_settings()

TERMINAL_STATUSES = ("done", "failed")
_DAY = timedelta(days=1)


class SubmissionNotFoundError(Exception):
    pass


class InputTypeDisabledError(Exception):
    pass


class SubmissionQuotaError(Exception):
    """The user spent part of their budget; `message` says which one."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


async def _check_quota(
    db: AsyncSession, redis_client: redis_asyncio.Redis, user_id: uuid.UUID
) -> None:
    # Cheapest checks first; the burst limit also caps how hard a script can
    # hit the two queries below.
    try:
        await check_rate_limit(
            f"submit:user:{user_id}",
            settings.rate_limit_submissions_per_minute,
            client=redis_client,
        )
    except RateLimitExceeded as exc:
        raise SubmissionQuotaError(
            "Enviaste demasiados casos seguidos. Espera un momento.", exc.retry_after_seconds
        ) from exc

    active = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(Submission.user_id == user_id, Submission.status.not_in(TERMINAL_STATUSES))
    )
    if active >= settings.max_active_submissions_per_user:
        raise SubmissionQuotaError(
            "Ya tienes casos en curso. Espera a que terminen para enviar otro.", 30
        )

    # Persisted rather than in Redis, so the daily cap survives a Redis flush.
    since = datetime.now(UTC) - _DAY
    recent = await db.execute(
        select(Submission.created_at)
        .where(Submission.user_id == user_id, Submission.created_at >= since)
        .order_by(Submission.created_at)
    )
    created = list(recent.scalars().all())
    if len(created) >= settings.max_submissions_per_day:
        oldest = created[0] if created[0].tzinfo else created[0].replace(tzinfo=UTC)
        retry_after = int((oldest + _DAY - datetime.now(UTC)).total_seconds())
        raise SubmissionQuotaError(
            "Alcanzaste el límite diario de casos. Intenta de nuevo mañana.",
            max(retry_after, 1),
        )


async def create_submission(
    db: AsyncSession,
    redis_client: redis_asyncio.Redis,
    *,
    user_id: uuid.UUID,
    input_type: str,
    raw_input: str,
) -> Submission:
    if input_type == "video" and not settings.video_ingest_enabled:
        raise InputTypeDisabledError()

    await _check_quota(db, redis_client, user_id)

    submission = Submission(
        user_id=user_id,
        input_type=input_type,
        raw_input=raw_input,
        status="queued",
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    await enqueue("run_pipeline", str(submission.id))

    return submission


async def get_submission(
    db: AsyncSession, *, submission_id: uuid.UUID, user_id: uuid.UUID
) -> Submission:
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id, Submission.user_id == user_id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise SubmissionNotFoundError()
    return submission


async def list_submissions(db: AsyncSession, *, user_id: uuid.UUID) -> list[Submission]:
    result = await db.execute(
        select(Submission)
        .where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc())
    )
    return list(result.scalars().all())
