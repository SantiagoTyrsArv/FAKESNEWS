import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.auth.models import User
from app.modules.submissions import service as submissions_service
from app.modules.submissions import ws_tickets

PASSWORD = "Str0ngPassw0rd!"


async def _login(client: AsyncClient, email: str = "ticket@example.com") -> None:
    client.cookies.clear()
    await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.json()["status"] == "authenticated"


def _csrf(client: AsyncClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


async def _create_case(client: AsyncClient, monkeypatch) -> str:
    async def fake_enqueue(*_args) -> None:
        return None

    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    resp = await client.post(
        "/submissions",
        json={"input_type": "text", "raw_input": "El cielo es azul."},
        headers=_csrf(client),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_ws_ticket_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.post(f"/submissions/{uuid.uuid4()}/ws-ticket")
    assert resp.status_code == 401


async def test_ws_ticket_requires_csrf(app_client: AsyncClient, monkeypatch) -> None:
    await _login(app_client)
    case_id = await _create_case(app_client, monkeypatch)

    resp = await app_client.post(f"/submissions/{case_id}/ws-ticket")

    assert resp.status_code == 403


async def test_ws_ticket_for_own_case(
    app_client: AsyncClient, db_session, fake_redis, monkeypatch
) -> None:
    await _login(app_client)
    case_id = await _create_case(app_client, monkeypatch)
    user = (await db_session.execute(select(User))).scalar_one()

    resp = await app_client.post(f"/submissions/{case_id}/ws-ticket", headers=_csrf(app_client))

    assert resp.status_code == 200
    body = resp.json()
    assert body["expires_in"] == 30
    key = f"ws-ticket:{body['ticket']}"
    assert fake_redis._values[key] == f"{user.id}:{case_id}"
    assert fake_redis._ttls[key] == 30


async def test_ws_ticket_for_someone_elses_case_is_404(
    app_client: AsyncClient, monkeypatch
) -> None:
    await _login(app_client, "owner@example.com")
    case_id = await _create_case(app_client, monkeypatch)
    await _login(app_client, "intruder@example.com")

    resp = await app_client.post(f"/submissions/{case_id}/ws-ticket", headers=_csrf(app_client))

    assert resp.status_code == 404


async def test_redeem_ticket_is_single_use(fake_redis) -> None:
    user_id, case_id = uuid.uuid4(), uuid.uuid4()
    ticket = await ws_tickets.issue_ticket(fake_redis, user_id=user_id, submission_id=case_id)

    assert await ws_tickets.redeem_ticket(fake_redis, ticket) == (user_id, case_id)
    assert await ws_tickets.redeem_ticket(fake_redis, ticket) is None


async def test_redeem_ticket_rejects_garbage(fake_redis) -> None:
    await fake_redis.set("ws-ticket:bad", "no-separator", ex=30)

    assert await ws_tickets.redeem_ticket(fake_redis, "x" * 200) is None
    assert await ws_tickets.redeem_ticket(fake_redis, "bad") is None
    assert await ws_tickets.redeem_ticket(fake_redis, "missing") is None


async def test_ws_ticket_is_rate_limited(app_client: AsyncClient, monkeypatch) -> None:
    await _login(app_client)
    case_id = await _create_case(app_client, monkeypatch)
    monkeypatch.setattr(submissions_service.settings, "rate_limit_ws_ticket_per_minute", 2)

    codes = [
        (
            await app_client.post(f"/submissions/{case_id}/ws-ticket", headers=_csrf(app_client))
        ).status_code
        for _ in range(3)
    ]

    assert codes == [200, 200, 429]
