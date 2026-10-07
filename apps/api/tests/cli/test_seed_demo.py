from types import SimpleNamespace

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import seed_demo
from app.modules.auth.models import MfaRecoveryCode, User
from app.modules.sources.models import Source, SourceScoreEvent
from app.modules.submissions.models import Submission


async def _count(db: AsyncSession, model) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def test_seed_creates_mfa_user_and_demo_cases(db_session: AsyncSession) -> None:
    result = await seed_demo.seed(db_session)

    assert result.user_created is True
    assert result.cases_created == len(seed_demo.DEMO_CASES)
    assert result.sources_added > 0
    assert len(result.recovery_codes) == 10

    user = (
        await db_session.execute(select(User).where(User.email == seed_demo.DEMO_EMAIL))
    ).scalar_one()
    assert user.mfa_enabled is True

    statuses = sorted((await db_session.execute(select(Submission.status))).scalars().all())
    assert statuses == ["done", "done", "failed"]
    raw_inputs = (await db_session.execute(select(Submission.raw_input))).scalars().all()
    assert all(r.startswith(seed_demo.DEMO_MARKER) for r in raw_inputs)


async def test_seed_does_not_touch_source_reputation(db_session: AsyncSession) -> None:
    await seed_demo.seed(db_session)

    assert await _count(db_session, SourceScoreEvent) == 0
    counts = (await db_session.execute(select(Source.cases_count))).scalars().all()
    assert set(counts) == {0}


async def test_seed_is_idempotent_and_keeps_totp_secret(db_session: AsyncSession) -> None:
    first = await seed_demo.seed(db_session)
    second = await seed_demo.seed(db_session)

    assert second.user_created is False
    assert second.cases_created == 0
    assert second.sources_added == 0
    assert second.totp_secret == first.totp_secret
    assert second.recovery_codes != first.recovery_codes
    assert await _count(db_session, User) == 1
    assert await _count(db_session, Submission) == len(seed_demo.DEMO_CASES)
    assert await _count(db_session, MfaRecoveryCode) == 10


async def test_seed_refuses_production(db_session: AsyncSession, monkeypatch) -> None:
    monkeypatch.setattr(
        seed_demo, "get_settings", lambda: SimpleNamespace(environment="production")
    )

    with pytest.raises(seed_demo.ProductionSeedError):
        await seed_demo.seed(db_session)
    assert await _count(db_session, User) == 0


async def test_seeded_user_can_log_in_and_read_a_report(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    result = await seed_demo.seed(db_session)

    login_resp = await app_client.post(
        "/auth/login", json={"email": result.email, "password": result.password}
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["token_type"] == "mfa_pending"

    verify_resp = await app_client.post(
        "/auth/2fa/verify",
        json={"code": pyotp.TOTP(result.totp_secret).now()},
        headers={"Authorization": f"Bearer {login_resp.json()['token']}"},
    )
    assert verify_resp.status_code == 200

    done_id = result.case_ids[0]
    report = (await app_client.get(f"/reports/{done_id}")).json()
    assert report["summary"] == {
        "total_claims": 3,
        "supported": 1,
        "contradicted": 1,
        "insufficient": 1,
    }
    first_claim = report["claims"][0]
    assert first_claim["verdict"] == "SUPPORTED"
    assert len(first_claim["evidence"]) == 3
    assert all(seed_demo.ILLUSTRATIVE in e["snippet"] for e in first_claim["evidence"])


def _production(monkeypatch) -> None:
    monkeypatch.setattr(
        seed_demo, "get_settings", lambda: SimpleNamespace(environment="production")
    )


async def test_production_seed_uses_a_random_password(
    app_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    _production(monkeypatch)

    result = await seed_demo.seed(db_session, allow_production=True)

    assert result.password != seed_demo.DEMO_PASSWORD
    assert len(result.password) >= 20
    ok = await app_client.post(
        "/auth/login", json={"email": result.email, "password": result.password}
    )
    assert ok.json()["token_type"] == "mfa_pending"
    public = await app_client.post(
        "/auth/login", json={"email": result.email, "password": seed_demo.DEMO_PASSWORD}
    )
    assert public.status_code == 401


async def test_production_seed_rotates_the_password_on_each_run(
    db_session: AsyncSession, monkeypatch
) -> None:
    _production(monkeypatch)

    first = await seed_demo.seed(db_session, allow_production=True)
    second = await seed_demo.seed(db_session, allow_production=True)

    assert first.password != second.password
    assert second.cases_created == 0
