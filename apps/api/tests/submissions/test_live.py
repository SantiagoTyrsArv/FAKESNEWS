"""The case progress WebSocket (requirement: WebSockets).

Synchronous tests on Starlette's TestClient, the only client here that speaks
WebSocket. Everything async (the in-memory database, FakeRedis queues) runs in
the TestClient's own event loop, through client.portal.
"""

import json
from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.db import Base, get_db
from app.core.rate_limit import get_redis_dependency
from app.modules.submissions import events, live
from app.modules.submissions import service as submissions_service

ORIGIN = "https://fakesnews.vercel.app"
PASSWORD = "Str0ngPassw0rd!"


@pytest.fixture
def client(fake_redis, monkeypatch) -> Iterator[TestClient]:
    import app.core.models_registry  # noqa: F401 - populates Base.metadata
    from app.main import app

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    async def create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def fake_enqueue(*_args) -> None:
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dependency] = lambda: fake_redis
    monkeypatch.setattr(submissions_service, "enqueue", fake_enqueue)
    monkeypatch.setattr(submissions_service.settings, "max_active_submissions_per_user", 10)
    monkeypatch.setattr(live.settings, "cors_origins", [ORIGIN])
    with TestClient(app) as test_client:
        test_client.portal.call(create_schema)
        test_client.fake_redis = fake_redis
        yield test_client
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str = "live@example.com") -> None:
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    resp = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.json()["status"] == "authenticated"


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies.get("csrf_token")}


def _case(client: TestClient) -> str:
    resp = client.post(
        "/submissions",
        json={"input_type": "text", "raw_input": "El cielo es azul."},
        headers=_csrf(client),
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _ticket(client: TestClient, case_id: str) -> str:
    resp = client.post(f"/submissions/{case_id}/ws-ticket", headers=_csrf(client))
    assert resp.status_code == 200
    return resp.json()["ticket"]


def _connect(client: TestClient, case_id: str, ticket: str, origin: str | None = ORIGIN):
    headers = {"origin": origin} if origin else {}
    return client.websocket_connect(f"/ws/submissions/{case_id}?ticket={ticket}", headers=headers)


def _publish(client: TestClient, case_id: str, status: str, error: str | None = None) -> None:
    payload = json.dumps({"status": status, "error": error})
    client.portal.call(client.fake_redis.publish, events.channel_name(case_id), payload)


@pytest.fixture
def case(client: TestClient) -> str:
    _login(client)
    return _case(client)


def test_rejects_a_foreign_origin(client: TestClient, case: str) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        _connect(client, case, _ticket(client, case), origin="https://evil.example"),
    ):
        pass


def test_rejects_a_missing_origin(client: TestClient, case: str) -> None:
    with (
        pytest.raises(WebSocketDisconnect),
        _connect(client, case, _ticket(client, case), origin=None),
    ):
        pass


def test_rejects_an_invalid_ticket(client: TestClient, case: str) -> None:
    with pytest.raises(WebSocketDisconnect), _connect(client, case, "nope"):
        pass


def test_ticket_cannot_be_reused(client: TestClient, case: str) -> None:
    ticket = _ticket(client, case)
    with _connect(client, case, ticket) as ws:
        assert ws.receive_json()["status"] == "queued"

    with pytest.raises(WebSocketDisconnect), _connect(client, case, ticket):
        pass


def test_rejects_a_ticket_for_another_case(client: TestClient, case: str) -> None:
    other = _case(client)
    with pytest.raises(WebSocketDisconnect), _connect(client, other, _ticket(client, case)):
        pass


def test_sends_current_status_first(client: TestClient, case: str) -> None:
    with _connect(client, case, _ticket(client, case)) as ws:
        assert ws.receive_json() == {"status": "queued", "error": None}


def test_forwards_published_status_and_closes_on_done(client: TestClient, case: str) -> None:
    with _connect(client, case, _ticket(client, case)) as ws:
        ws.receive_json()
        _publish(client, case, "verifying")
        assert ws.receive_json() == {"status": "verifying", "error": None}
        _publish(client, case, "done")
        assert ws.receive_json() == {"status": "done", "error": None}
        assert ws.receive() == {"type": "websocket.close", "code": 1000, "reason": ""}


def test_subscribes_before_reading_the_status(client: TestClient, case: str, monkeypatch) -> None:
    original = submissions_service.get_submission

    async def publishes_while_reading(db, **kwargs):
        await client.fake_redis.publish(
            events.channel_name(case), json.dumps({"status": "extracting", "error": None})
        )
        return await original(db, **kwargs)

    monkeypatch.setattr(submissions_service, "get_submission", publishes_while_reading)
    monkeypatch.setattr(live.settings, "ws_max_seconds", 2)
    with _connect(client, case, _ticket(client, case)) as ws:
        assert ws.receive_json()["status"] == "queued"
        assert ws.receive_json() == {"status": "extracting", "error": None}


def test_closes_after_ws_max_seconds(client: TestClient, case: str, monkeypatch) -> None:
    monkeypatch.setattr(live.settings, "ws_max_seconds", 1)
    with _connect(client, case, _ticket(client, case)) as ws:
        ws.receive_json()
        assert ws.receive()["type"] == "websocket.close"


def test_a_message_from_the_client_does_not_end_the_stream(client: TestClient, case: str) -> None:
    with _connect(client, case, _ticket(client, case)) as ws:
        ws.receive_json()
        ws.send_text("hola")
        _publish(client, case, "scoring")
        assert ws.receive_json() == {"status": "scoring", "error": None}


def test_caps_open_sockets_per_user(client: TestClient, case: str, monkeypatch) -> None:
    # Each socket holds a Redis pub/sub connection for up to WS_MAX_SECONDS:
    # one account must not be able to pile them up.
    monkeypatch.setattr(live.settings, "ws_max_sockets_per_user", 1)
    with _connect(client, case, _ticket(client, case)) as first:
        first.receive_json()
        with pytest.raises(WebSocketDisconnect), _connect(client, case, _ticket(client, case)):
            pass

    with _connect(client, case, _ticket(client, case)) as again:
        assert again.receive_json()["status"] == "queued"
