import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import enqueue
from app.modules.submissions.models import Submission


class SubmissionNotFoundError(Exception):
    pass


async def create_submission(
    db: AsyncSession, *, user_id: uuid.UUID, input_type: str, raw_input: str
) -> Submission:
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
