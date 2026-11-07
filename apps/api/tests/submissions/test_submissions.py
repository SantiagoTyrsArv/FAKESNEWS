import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select

from app.core.config import get_settings
from app.modules.auth.models import User
from app.modules.pipeline.models import Claim
from app.modules.submissions import service as submissions_service
from app.modules.submissions.models import Submission

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


async def _add_claim_created_at(db_session, created_at: datetime) -> None:
    submission = (await db_session.execute(select(Submission))).scalars().first()
    db_session.add(
        Claim(
            submission_id=submission.id,
            text="Afirmación.",
            verdict="INSUFFICIENT",
            rationale="Sin fuentes.",
            created_at=created_at,
        )
    )
    await db_session.commit()


async def test_submissions_stop_at_the_monthly_claim_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_month", 1)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201
    await _mark_all(db_session, "done")
    await _add_claim_created_at(db_session, datetime.now(UTC))

    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert "cuota mensual" in resp.json()["detail"]
    assert int(resp.headers["Retry-After"]) > 0


async def test_claims_from_last_month_do_not_count_towards_the_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_month", 1)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201
    await _mark_all(db_session, "done")
    await _add_claim_created_at(db_session, datetime.now(UTC) - timedelta(days=40))

    assert (await _post_text(app_client)).status_code == 201


async def test_cases_in_flight_count_towards_the_monthly_cap(
    app_client: AsyncClient, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_submission", 4)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_month", 4)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201

    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert "cuota mensual" in resp.json()["detail"]


async def test_a_stuck_case_stops_counting_towards_the_monthly_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_submission", 4)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_month", 4)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201
    stuck = (await db_session.execute(select(Submission))).scalars().one()
    stuck.created_at = datetime.now(UTC) - timedelta(hours=2)
    await db_session.commit()

    assert (await _post_text(app_client)).status_code == 201


async def test_one_account_stops_at_its_own_monthly_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_account_per_month", 1)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201
    await _mark_all(db_session, "done")
    await _add_claim_created_at(db_session, datetime.now(UTC))

    resp = await _post_text(app_client)

    assert resp.status_code == 429
    assert "tu límite mensual" in resp.json()["detail"]


async def test_other_accounts_claims_do_not_use_your_monthly_cap(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_claims_per_account_per_month", 1)
    await _login_full_session(app_client)
    assert (await _post_text(app_client)).status_code == 201
    await _mark_all(db_session, "done")
    other = User(email="otra@example.com", password_hash="x")
    db_session.add(other)
    await db_session.flush()
    theirs = Submission(user_id=other.id, input_type="text", raw_input="x", status="done")
    db_session.add(theirs)
    await db_session.flush()
    db_session.add(Claim(submission_id=theirs.id, text="a", verdict="INSUFFICIENT", rationale="r"))
    await db_session.commit()

    assert (await _post_text(app_client)).status_code == 201


def test_default_limits() -> None:
    settings = get_settings()

    assert settings.max_claims_per_month == 450
    assert settings.max_claims_per_account_per_month == 60
    assert settings.max_submissions_per_day == 5
    assert settings.max_claims_per_submission == 4
    assert settings.verify_concurrency_limit == 2


async def _prepare(client: AsyncClient, monkeypatch) -> None:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    await _login_full_session(client)


async def _age_all(db_session, minutes: int) -> None:
    from sqlalchemy import update

    await db_session.execute(
        update(Submission).values(created_at=datetime.now(UTC) - timedelta(minutes=minutes))
    )
    await db_session.commit()


async def test_failed_enqueue_fails_the_case_and_frees_the_slot(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    async def broken_enqueue(job_name: str, *args) -> None:
        raise RedisConnectionError("redis is down")

    monkeypatch.setattr(submissions_service, "enqueue", broken_enqueue)
    await _login_full_session(app_client)

    resp = await _post_text(app_client)

    assert resp.status_code == 503
    assert "Retry-After" in resp.headers
    submission = (await db_session.execute(select(Submission))).scalar_one()
    await db_session.refresh(submission)
    assert submission.status == "failed"
    assert submission.error == submissions_service.ENQUEUE_FAILURE


async def test_stuck_case_stops_blocking_the_user(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(submissions_service.settings, "max_active_submissions_per_user", 1)
    await _prepare(app_client, monkeypatch)
    assert (await _post_text(app_client)).status_code == 201
    await _age_all(db_session, 21)

    assert (await _post_text(app_client)).status_code == 201

    listed = (await app_client.get("/submissions")).json()["submissions"]
    assert sorted(s["status"] for s in listed) == ["failed", "queued"]


async def test_stuck_case_shows_as_failed_on_its_page(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    await _prepare(app_client, monkeypatch)
    case = (await _post_text(app_client)).json()
    await _age_all(db_session, 21)

    body = (await app_client.get(f"/submissions/{case['id']}")).json()

    assert body["status"] == "failed"
    assert body["error"] == submissions_service.STUCK_FAILURE


async def test_case_within_the_time_limit_is_left_alone(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    await _prepare(app_client, monkeypatch)
    case = (await _post_text(app_client)).json()
    await _age_all(db_session, 19)

    body = (await app_client.get(f"/submissions/{case['id']}")).json()

    assert body["status"] == "queued"


async def test_finished_case_is_not_marked_stuck(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    await _prepare(app_client, monkeypatch)
    case = (await _post_text(app_client)).json()
    await _mark_all(db_session, "done")
    await _age_all(db_session, 60)

    body = (await app_client.get(f"/submissions/{case['id']}")).json()

    assert body["status"] == "done"
    assert body["error"] is None


async def test_stuck_case_of_another_user_is_left_alone(
    app_client: AsyncClient, db_session, monkeypatch
) -> None:
    await _prepare(app_client, monkeypatch)
    other = User(email="other@example.com", password_hash="x")
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        Submission(
            user_id=other.id,
            input_type="text",
            raw_input="otro",
            status="verifying",
            created_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.commit()

    await app_client.get("/submissions")

    theirs = await db_session.scalar(select(Submission).where(Submission.user_id == other.id))
    assert theirs.status == "verifying"


async def _seed_cases(db_session, count: int, *, raw_input: str = "caso") -> None:
    user = await db_session.scalar(select(User).where(User.email == EMAIL))
    now = datetime.now(UTC)
    for minute in range(count):
        db_session.add(
            Submission(
                user_id=user.id,
                input_type="text",
                raw_input=f"{raw_input} {minute}",
                status="done",
                # Pairs share a timestamp: the id has to break the tie.
                created_at=now - timedelta(minutes=minute // 2),
            )
        )
    await db_session.commit()


async def test_list_walks_every_case_once_newest_first(app_client: AsyncClient, db_session) -> None:
    await _login_full_session(app_client)
    await _seed_cases(db_session, 7)

    seen: list[dict] = []
    cursor = None
    for _ in range(4):
        params = {"limit": 3} | ({"cursor": cursor} if cursor else {})
        page = (await app_client.get("/submissions", params=params)).json()
        seen += page["submissions"]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 7
    assert len({s["id"] for s in seen}) == 7
    dates = [s["created_at"] for s in seen]
    assert dates == sorted(dates, reverse=True)


async def test_last_full_page_has_no_cursor(app_client: AsyncClient, db_session) -> None:
    await _login_full_session(app_client)
    await _seed_cases(db_session, 3)

    page = (await app_client.get("/submissions", params={"limit": 3})).json()

    assert len(page["submissions"]) == 3
    assert page["next_cursor"] is None


async def test_list_has_a_default_page_size(app_client: AsyncClient, db_session) -> None:
    await _login_full_session(app_client)
    await _seed_cases(db_session, submissions_service.DEFAULT_PAGE_SIZE + 1)

    page = (await app_client.get("/submissions")).json()

    assert len(page["submissions"]) == submissions_service.DEFAULT_PAGE_SIZE
    assert page["next_cursor"] is not None


async def test_list_rejects_a_page_over_the_maximum(app_client: AsyncClient) -> None:
    await _login_full_session(app_client)

    resp = await app_client.get(
        "/submissions", params={"limit": submissions_service.MAX_PAGE_SIZE + 1}
    )

    assert resp.status_code == 422


async def test_list_rejects_a_forged_cursor(app_client: AsyncClient) -> None:
    await _login_full_session(app_client)

    resp = await app_client.get("/submissions", params={"cursor": "no-es-un-cursor"})

    assert resp.status_code == 400


async def test_list_shortens_the_input_but_the_case_keeps_it(
    app_client: AsyncClient, db_session
) -> None:
    await _login_full_session(app_client)
    await _seed_cases(db_session, 1, raw_input="x" * 5000)

    listed = (await app_client.get("/submissions")).json()["submissions"][0]
    full = (await app_client.get(f"/submissions/{listed['id']}")).json()

    assert len(listed["raw_input"]) == submissions_service.LIST_PREVIEW_CHARS
    assert len(full["raw_input"]) > 5000
