import uuid
from urllib.parse import parse_qs, urlparse

import pyotp
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import User
from app.modules.pipeline.models import Claim, Evidence
from app.modules.sources.models import Source
from app.modules.submissions.models import Submission

PASSWORD = "Str0ngPassw0rd!"


def _secret_from_uri(uri: str) -> str:
    return dict(parse_qs(urlparse(uri).query))["secret"][0]


async def _login_full_session(client: AsyncClient, email: str) -> None:
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login_resp.json()['token']}"}

    setup_resp = await client.post("/auth/2fa/setup", headers=headers)
    code = pyotp.TOTP(_secret_from_uri(setup_resp.json()["otpauth_uri"])).now()
    await client.post("/auth/2fa/confirm", json={"code": code}, headers=headers)

    verify_resp = await client.post("/auth/2fa/verify", json={"code": code}, headers=headers)
    assert verify_resp.status_code == 200


async def _user_id(db_session: AsyncSession, email: str) -> uuid.UUID:
    result = await db_session.execute(select(User.id).where(User.email == email))
    return result.scalar_one()


async def _seed_done_case(db_session: AsyncSession, user_id: uuid.UUID) -> Submission:
    reuters = Source(domain="reuters.com", name="Reuters", type="agencia", alpha=8.0, beta=2.0)
    elpais = Source(
        domain="elpais.com", name="El País", type="medio", alpha=6.0, beta=2.0, cases_count=15
    )
    submission = Submission(
        user_id=user_id, input_type="text", raw_input="Texto de prueba.", status="done"
    )
    db_session.add_all([reuters, elpais, submission])
    await db_session.flush()

    supported = Claim(
        submission_id=submission.id,
        text="La inflación bajó en marzo.",
        verdict="SUPPORTED",
        rationale="Dos fuentes lo confirman.",
    )
    insufficient = Claim(
        submission_id=submission.id,
        text="El ministro renunció.",
        verdict="INSUFFICIENT",
        rationale="Sin evidencia verificable.",
    )
    db_session.add_all([supported, insufficient])
    await db_session.flush()

    db_session.add_all(
        [
            Evidence(
                claim_id=supported.id,
                source_id=reuters.id,
                url="https://www.reuters.com/a",
                snippet="La inflación cayó 0,3 puntos.",
                published_at="April 30, 2025",
                stance="supports",
            ),
            Evidence(
                claim_id=supported.id,
                source_id=elpais.id,
                url="https://elpais.com/b",
                snippet="Baja la inflación.",
                stance="supports",
            ),
        ]
    )
    await db_session.commit()
    return submission


async def test_report_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.get(f"/reports/{uuid.uuid4()}")
    assert resp.status_code == 401


async def test_report_for_done_case_includes_claims_evidence_and_sources(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_full_session(app_client, "owner@example.com")
    submission = await _seed_done_case(db_session, await _user_id(db_session, "owner@example.com"))

    resp = await app_client.get(f"/reports/{submission.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["submission"]["id"] == str(submission.id)
    assert body["submission"]["raw_input"] == "Texto de prueba."
    assert body["summary"] == {
        "total_claims": 2,
        "supported": 1,
        "contradicted": 0,
        "insufficient": 1,
    }
    assert body["disclaimer"]

    by_text = {c["text"]: c for c in body["claims"]}
    supported = by_text["La inflación bajó en marzo."]
    assert supported["verdict"] == "SUPPORTED"
    assert len(supported["evidence"]) == 2
    reuters_ev = next(e for e in supported["evidence"] if e["source"]["domain"] == "reuters.com")
    assert reuters_ev["url"] == "https://www.reuters.com/a"
    assert reuters_ev["published_at"] == "April 30, 2025"
    assert reuters_ev["stance"] == "supports"
    assert reuters_ev["source"]["score"] == 0.8
    assert reuters_ev["source"]["low_sample"] is True

    assert by_text["El ministro renunció."]["evidence"] == []


async def test_report_not_ready_returns_409(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_full_session(app_client, "owner@example.com")
    submission = Submission(
        user_id=await _user_id(db_session, "owner@example.com"),
        input_type="text",
        raw_input="x",
        status="verifying",
    )
    db_session.add(submission)
    await db_session.commit()

    resp = await app_client.get(f"/reports/{submission.id}")

    assert resp.status_code == 409


async def test_report_of_another_user_is_404(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _login_full_session(app_client, "owner@example.com")
    submission = await _seed_done_case(db_session, await _user_id(db_session, "owner@example.com"))

    app_client.cookies.clear()
    await _login_full_session(app_client, "intruder@example.com")

    resp = await app_client.get(f"/reports/{submission.id}")

    assert resp.status_code == 404
