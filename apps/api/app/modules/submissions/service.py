import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_asyncio
from redis.exceptions import RedisError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.queue import enqueue
from app.core.rate_limit import RateLimitExceeded, check_rate_limit
from app.modules.pipeline.models import Claim
from app.modules.submissions.models import Submission

settings = get_settings()
logger = get_logger(__name__)

TERMINAL_STATUSES = ("done", "failed")
ENQUEUE_FAILURE = "No se pudo poner el caso en cola. Envíalo de nuevo en un momento."
STUCK_FAILURE = "El análisis no terminó a tiempo. Envía el caso de nuevo."
_DAY = timedelta(days=1)
_IN_FLIGHT_WINDOW = timedelta(hours=1)
# Past the job timeout, nothing is working on a case. With this margin the
# limit is 20 minutes, when the query in infra/modules/worker.bicep also stops
# waking the worker: a case still queued by then will never start.
_STUCK_MARGIN = timedelta(minutes=5)


class SubmissionNotFoundError(Exception):
    pass


class InputTypeDisabledError(Exception):
    pass


class SubmissionEnqueueError(Exception):
    pass


class SubmissionQuotaError(Exception):
    """The user spent part of their budget; `message` says which one."""

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.message = message
        self.retry_after_seconds = retry_after_seconds


async def _fail_stuck_cases(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Close the user's cases nothing will ever finish: the job or the queue
    was lost. It runs on the API, not on a schedule in the worker, because the
    worker scales to zero once no recent case is pending."""
    limit = timedelta(seconds=settings.pipeline_job_timeout_seconds) + _STUCK_MARGIN
    result = await db.execute(
        update(Submission)
        .where(
            Submission.user_id == user_id,
            Submission.status.not_in(TERMINAL_STATUSES),
            Submission.created_at < datetime.now(UTC) - limit,
        )
        .values(status="failed", error=STUCK_FAILURE)
    )
    if result.rowcount:
        logger.warning("submissions_marked_stuck", user_id=str(user_id), count=result.rowcount)
        await db.commit()


async def _serialize_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Make one user's submissions take turns until commit, so parallel ones
    can't all pass the quota. SQLite has no advisory locks."""
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(select(func.pg_advisory_xact_lock(user_id.int % 2**63)))


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

    await _check_monthly_claims(db, user_id)


async def _check_monthly_claims(db: AsyncSession, user_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    seconds_left = int(((month_start + timedelta(days=32)).replace(day=1) - now).total_seconds())

    own_claims = await db.scalar(
        select(func.count())
        .select_from(Claim)
        .join(Submission, Claim.submission_id == Submission.id)
        .where(Submission.user_id == user_id, Claim.created_at >= month_start)
    )
    if own_claims >= settings.max_claims_per_account_per_month:
        raise SubmissionQuotaError(
            "Alcanzaste tu límite mensual de verificaciones. Vuelve el próximo mes.", seconds_left
        )

    claims = await db.scalar(
        select(func.count()).select_from(Claim).where(Claim.created_at >= month_start)
    )
    # Claims are saved when a case ends, so the ones in flight aren't rows yet.
    # Only recent ones count: a stuck case must not hold the quota forever.
    in_flight = await db.scalar(
        select(func.count())
        .select_from(Submission)
        .where(
            Submission.status.not_in(TERMINAL_STATUSES),
            Submission.created_at >= now - _IN_FLIGHT_WINDOW,
        )
    )
    if claims + in_flight * settings.max_claims_per_submission >= settings.max_claims_per_month:
        raise SubmissionQuotaError(
            "La cuota mensual de verificaciones se agotó. Vuelve el próximo mes.", seconds_left
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

    await _fail_stuck_cases(db, user_id)
    await _serialize_user(db, user_id)
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

    try:
        await enqueue("run_pipeline", str(submission.id))
    except (RedisError, OSError) as exc:
        # Without a job the case would count as active until it went stale.
        logger.error("submission_enqueue_failed", submission_id=str(submission.id), error=str(exc))
        submission.status = "failed"
        submission.error = ENQUEUE_FAILURE
        await db.commit()
        raise SubmissionEnqueueError() from exc

    return submission


async def get_submission(
    db: AsyncSession, *, submission_id: uuid.UUID, user_id: uuid.UUID
) -> Submission:
    await _fail_stuck_cases(db, user_id)
    result = await db.execute(
        select(Submission).where(Submission.id == submission_id, Submission.user_id == user_id)
    )
    submission = result.scalar_one_or_none()
    if submission is None:
        raise SubmissionNotFoundError()
    return submission


async def list_submissions(db: AsyncSession, *, user_id: uuid.UUID) -> list[Submission]:
    await _fail_stuck_cases(db, user_id)
    result = await db.execute(
        select(Submission)
        .where(Submission.user_id == user_id)
        .order_by(Submission.created_at.desc())
    )
    return list(result.scalars().all())
