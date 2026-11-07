"""The per-user quota must hold when one user submits in parallel."""

import asyncio
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.models import User
from app.modules.submissions import service
from app.modules.submissions.models import Submission
from tests.conftest import FakeRedis, requires_postgres

pytestmark = requires_postgres

Sessions = async_sessionmaker[AsyncSession]


async def _submit(sessions: Sessions, redis: FakeRedis, user_id: uuid.UUID) -> bool:
    async with sessions() as db:
        try:
            await service.create_submission(
                db, redis, user_id=user_id, input_type="text", raw_input="algo"
            )
        except service.SubmissionQuotaError:
            return False
        return True


async def test_parallel_submissions_respect_the_active_limit(
    pg_session_factory: Sessions, monkeypatch
) -> None:
    async def fake_enqueue(job_name: str, *args) -> None:
        return None

    monkeypatch.setattr(service, "enqueue", fake_enqueue)
    monkeypatch.setattr(service.settings, "max_active_submissions_per_user", 2)
    monkeypatch.setattr(service.settings, "rate_limit_submissions_per_minute", 100)

    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="x")
    async with pg_session_factory() as db:
        db.add(user)
        await db.commit()

    redis = FakeRedis()
    await asyncio.gather(*[_submit(pg_session_factory, redis, user.id) for _ in range(6)])

    async with pg_session_factory() as db:
        created = await db.scalar(
            select(func.count()).select_from(Submission).where(Submission.user_id == user.id)
        )
    assert created == 2
