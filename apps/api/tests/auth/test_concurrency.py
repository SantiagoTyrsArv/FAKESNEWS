"""Races the auth flows must win on Postgres. Each test runs two or more real
transactions at once, so none of them can be shown on SQLite."""

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth import service
from app.modules.auth.models import MfaRecoveryCode, RefreshToken, User
from app.modules.auth.recovery_codes import hash_recovery_code
from tests.conftest import FakeRedis, requires_postgres

pytestmark = requires_postgres

Sessions = async_sessionmaker[AsyncSession]

RECOVERY_CODE = "ABCD-EFGH-IJKL"
ROUNDS = 5


async def _user(sessions: Sessions, *, mfa: bool = False) -> uuid.UUID:
    user = User(
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        mfa_enabled=mfa,
        totp_secret_encrypted=None,
    )
    async with sessions() as db:
        db.add(user)
        await db.commit()
    return user.id


async def _rotate(sessions: Sessions, refresh: str) -> bool:
    async with sessions() as db:
        try:
            await service.rotate_refresh_token(db, refresh)
        except service.AuthError:
            return False
        return True


async def test_refresh_token_is_spent_once(pg_session_factory: Sessions) -> None:
    for _ in range(ROUNDS):
        user_id = await _user(pg_session_factory)
        async with pg_session_factory() as db:
            user = await db.get(User, user_id)
            session = await service.issue_session(db, user)

        outcomes = await asyncio.gather(
            _rotate(pg_session_factory, session["refresh_token"]),
            _rotate(pg_session_factory, session["refresh_token"]),
        )

        assert sorted(outcomes) == [False, True]
        async with pg_session_factory() as db:
            children = await db.scalar(
                select(func.count())
                .select_from(RefreshToken)
                .where(RefreshToken.user_id == user_id, RefreshToken.replaced_by.is_(None))
            )
        assert children == 1


async def _use_recovery_code(sessions: Sessions, user_id: uuid.UUID) -> bool:
    async with sessions() as db:
        user = await db.get(User, user_id)
        try:
            await service.verify_login(
                db,
                FakeRedis(),
                ip="203.0.113.1",
                user=user,
                code=None,
                recovery_code=RECOVERY_CODE,
            )
        except service.InvalidCodeError:
            return False
        return True


async def test_recovery_code_is_spent_once(pg_session_factory: Sessions) -> None:
    code_hash = await asyncio.to_thread(hash_recovery_code, RECOVERY_CODE)
    for _ in range(ROUNDS):
        user_id = await _user(pg_session_factory, mfa=True)
        async with pg_session_factory() as db:
            db.add(MfaRecoveryCode(user_id=user_id, code_hash=code_hash))
            await db.commit()

        outcomes = await asyncio.gather(
            _use_recovery_code(pg_session_factory, user_id),
            _use_recovery_code(pg_session_factory, user_id),
        )

        assert sorted(outcomes) == [False, True]


async def _fail_once(sessions: Sessions, user_id: uuid.UUID) -> None:
    async with sessions() as db:
        await service._register_failed_attempt(db, await db.get(User, user_id))


async def test_failed_attempts_are_all_counted(pg_session_factory: Sessions) -> None:
    user_id = await _user(pg_session_factory)

    await asyncio.gather(*[_fail_once(pg_session_factory, user_id) for _ in range(4)])

    async with pg_session_factory() as db:
        user = await db.get(User, user_id)
    assert user.failed_attempts == 4


@pytest.mark.parametrize("attempts", [service.settings.max_login_attempts])
async def test_concurrent_failures_reach_the_lockout(
    pg_session_factory: Sessions, attempts: int
) -> None:
    user_id = await _user(pg_session_factory)

    await asyncio.gather(*[_fail_once(pg_session_factory, user_id) for _ in range(attempts)])

    async with pg_session_factory() as db:
        user = await db.get(User, user_id)
    assert user.locked_until is not None
    assert user.locked_until > service._now() + timedelta(minutes=1)
