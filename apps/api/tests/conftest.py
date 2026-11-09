import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long-for-hs256")
os.environ.setdefault("TOTP_SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires live Postgres/Redis (docker compose)")


requires_integration = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") != "1",
    reason="set RUN_INTEGRATION_TESTS=1 with docker compose services running",
)


class FakePubSub:
    """In-memory stand-in for redis-py's async PubSub: subscribe/unsubscribe,
    get_message (with timeout) and aclose. Each subscriber gets its own queue,
    created on subscribe, so it must be used from the loop that publishes."""

    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self.channels: set[str] = set()

    async def subscribe(self, *channels: str) -> None:
        for channel in channels:
            self.channels.add(channel)
            self._redis._subscribers.setdefault(channel, []).append(self._queue)
            self._queue.put_nowait({"type": "subscribe", "channel": channel, "data": 1})

    async def unsubscribe(self, *channels: str) -> None:
        for channel in channels or tuple(self.channels):
            self.channels.discard(channel)
            queues = self._redis._subscribers.get(channel, [])
            if self._queue in queues:
                queues.remove(self._queue)

    async def get_message(
        self, ignore_subscribe_messages: bool = False, timeout: float = 0.0
    ) -> dict | None:
        while True:
            try:
                message = await asyncio.wait_for(self._queue.get(), timeout=max(timeout, 0.001))
            except TimeoutError:
                return None
            if ignore_subscribe_messages and message["type"] != "message":
                continue
            return message

    async def aclose(self) -> None:
        await self.unsubscribe()


class FakeRedis:
    """Minimal in-memory stand-in for the subset of redis-py's async API the
    app actually uses: incr/expire/ttl (rate limiting), set/getdel (single-use
    tokens), publish/pubsub (case progress events), ping/aclose.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._ttls: dict[str, int] = {}
        self._values: dict[str, str] = {}
        self._subscribers: dict[str, list[asyncio.Queue[dict]]] = {}

    async def publish(self, channel: str, message: str) -> int:
        queues = self._subscribers.get(channel, [])
        for queue in queues:
            queue.put_nowait({"type": "message", "channel": channel, "data": message})
        return len(queues)

    def pubsub(self) -> FakePubSub:
        return FakePubSub(self)

    async def getdel(self, key: str) -> str | None:
        self._ttls.pop(key, None)
        return self._values.pop(key, None)

    async def incr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]

    async def decr(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) - 1
        return self._counters[key]

    async def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = seconds

    async def set(
        self, key: str, value: str, *, nx: bool = False, ex: int | None = None
    ) -> bool | None:
        if nx and key in self._values:
            return None
        self._values[key] = value
        if ex is not None:
            self._ttls[key] = ex
        return True

    async def ttl(self, key: str) -> int:
        return self._ttls.get(key, 60)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        return None


@pytest_asyncio.fixture
async def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture(autouse=True)
def _events_use_fake_redis(fake_redis: FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status changes publish to Redis (case progress over WebSocket). No test
    should reach a real server for that: route them to the test's FakeRedis."""
    try:
        from app.modules.submissions import events
    except ImportError:
        return
    monkeypatch.setattr(events, "get_redis", lambda: fake_redis)


@pytest_asyncio.fixture
async def db_session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    import app.core.models_registry  # noqa: F401 - populates Base.metadata
    from app.core.db import Base

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield session_factory

    await engine.dispose()


requires_postgres = pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="set TEST_POSTGRES_URL to a throwaway database: row locks do nothing on SQLite",
)


@pytest_asyncio.fixture
async def pg_session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Real Postgres with a fresh schema, for what SQLite cannot show."""
    import app.core.models_registry  # noqa: F401 - populates Base.metadata
    from app.core.db import Base

    engine = create_async_engine(os.environ["TEST_POSTGRES_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield async_sessionmaker(engine, expire_on_commit=False)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with db_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app_client(
    db_session: AsyncSession, fake_redis: FakeRedis
) -> AsyncGenerator[AsyncClient, None]:
    from app.core.db import get_db
    from app.core.rate_limit import get_redis_dependency
    from app.main import app

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    def override_get_redis() -> FakeRedis:
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_dependency] = override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
