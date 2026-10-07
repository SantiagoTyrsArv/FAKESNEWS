import uuid
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient

from app.modules.submissions import service as submissions_service

EMAIL = "sub@example.com"
PASSWORD = "Str0ngPassw0rd!"


def _secret_from_uri(uri: str) -> str:
    return dict(parse_qs(urlparse(uri).query))["secret"][0]


async def _login_full_session(client: AsyncClient) -> None:
    await client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    login_resp = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login_resp.json()["status"] == "authenticated"


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


async def _post_text(client: AsyncClient, text: str = "El cielo es azul."):
    return await client.post(
        "/submissions",
        json={"input_type": "text", "raw_input": text},
        headers={"X-CSRF-Token": client.cookies.get("csrf_token")},
    )


async def _mark_all(db_session, status: str) -> None:
    from sqlalchemy import update

    from app.modules.submissions.models import Submission

    await db_session.execute(update(Submission).values(status=status))
    await db_session.commit()


async def test_submissions_are_rate_limited_per_minute(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "rate_limit_submissions_per_minute", 2)
    await _login_full_session(app_client)

    for _ in range(2):
        assert (await _post_text(app_client)).status_code == 201
        await _mark_all(db_session, "done")  # keep the in-flight cap out of the way

    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) >= 1


async def test_submissions_have_a_daily_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_submissions_per_day", 2)
    await _login_full_session(app_client)

    for _ in range(2):
        assert (await _post_text(app_client)).status_code == 201
        await _mark_all(db_session, "done")

    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert "diario" in resp.json()["detail"]


async def test_submissions_cap_cases_in_flight(app_client: AsyncClient, monkeypatch) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_active_submissions_per_user", 1)
    await _login_full_session(app_client)

    assert (await _post_text(app_client)).status_code == 201  # stays "queued"
    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert "en curso" in resp.json()["detail"]


async def test_rejected_submission_is_not_stored_or_enqueued(
    app_client: AsyncClient, monkeypatch
) -> None:
    enqueued: list = []

    async def fake_enqueue(*args) -> None:
        enqueued.append(args)

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_active_submissions_per_user", 1)
    await _login_full_session(app_client)

    await _post_text(app_client)
    await _post_text(app_client)

    assert len(enqueued) == 1
    assert len((await app_client.get("/submissions")).json()["submissions"]) == 1


async def test_video_submissions_rejected_when_disabled(
    app_client: AsyncClient, monkeypatch
) -> None:
    enqueued: list = []

    async def fake_enqueue(*args) -> None:
        enqueued.append(args)

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "video_ingest_enabled", False)
    await _login_full_session(app_client)

    resp = await app_client.post(
        "/submissions",
        json={"input_type": "video", "raw_input": "https://www.youtube.com/watch?v=x"},
        headers={"X-CSRF-Token": app_client.cookies.get("csrf_token")},
    )

    assert resp.status_code == 400
    assert "video" in resp.json()["detail"].lower()
    assert enqueued == []
