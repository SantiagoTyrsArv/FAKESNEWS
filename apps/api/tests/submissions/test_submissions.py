import uuid
from urllib.parse import parse_qs, urlparse

import pyotp
from httpx import AsyncClient

from app.modules.submissions import service as submissions_service

EMAIL = "sub@example.com"
PASSWORD = "Str0ngPassw0rd!"


def _secret_from_uri(uri: str) -> str:
    return dict(parse_qs(urlparse(uri).query))["secret"][0]


async def _login_full_session(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    login_resp = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    setup_resp = await client.post("/auth/2fa/setup", headers=headers)
    secret = _secret_from_uri(setup_resp.json()["otpauth_uri"])
    code = pyotp.TOTP(secret).now()
    await client.post("/auth/2fa/confirm", json={"code": code}, headers=headers)

    verify_resp = await client.post("/auth/2fa/verify", json={"code": code}, headers=headers)
    assert verify_resp.status_code == 200


async def test_create_submission_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.post("/submissions", json={"input_type": "text", "raw_input": "algo"})
    assert resp.status_code == 401


async def test_create_submission_requires_csrf(app_client: AsyncClient) -> None:
    await _login_full_session(app_client)

    resp = await app_client.post("/submissions", json={"input_type": "text", "raw_input": "algo"})

    assert resp.status_code == 403


async def test_create_and_fetch_submission(app_client: AsyncClient, monkeypatch) -> None:
    enqueued: list[tuple[str, tuple]] = []

    async def fake_enqueue(job_name: str, *args) -> None:
        enqueued.append((job_name, args))

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)

    await _login_full_session(app_client)
    csrf = app_client.cookies.get("csrf_token")

    create_resp = await app_client.post(
        "/submissions",
        json={"input_type": "text", "raw_input": "El cielo es azul."},
        headers={"X-CSRF-Token": csrf},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["status"] == "queued"
    assert body["input_type"] == "text"
    assert enqueued == [("run_pipeline", (body["id"],))]

    get_resp = await app_client.get(f"/submissions/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == body["id"]

    list_resp = await app_client.get("/submissions")
    assert list_resp.status_code == 200
    assert len(list_resp.json()["submissions"]) == 1


async def test_get_submission_not_found(app_client: AsyncClient) -> None:
    await _login_full_session(app_client)

    resp = await app_client.get(f"/submissions/{uuid.uuid4()}")

    assert resp.status_code == 404


async def test_create_submission_rejects_invalid_input_type(app_client: AsyncClient) -> None:
    await _login_full_session(app_client)
    csrf = app_client.cookies.get("csrf_token")

    resp = await app_client.post(
        "/submissions",
        json={"input_type": "carrier-pigeon", "raw_input": "algo"},
        headers={"X-CSRF-Token": csrf},
    )

    assert resp.status_code == 422
