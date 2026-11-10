import json
import uuid

from httpx import AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.pipeline import orchestrator
from app.modules.submissions import events
from app.modules.submissions import service as submissions_service
from app.modules.submissions.models import Submission

EMAIL = "events@example.com"
PASSWORD = "Str0ngPassw0rd!"


async def _next_status(pubsub) -> dict:
    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert message is not None, "nothing was published"
    return json.loads(message["data"])


async def _submission(db_session, status: str = "queued") -> Submission:
    user = User(email=EMAIL, password_hash=hash_password(PASSWORD))
    db_session.add(user)
    await db_session.commit()
    submission = Submission(user_id=user.id, input_type="text", raw_input="x", status=status)
    db_session.add(submission)
    await db_session.commit()
    await db_session.refresh(submission)
    return submission


def test_channel_name_is_per_case() -> None:
    case_id = uuid.uuid4()
    assert events.channel_name(case_id) == f"submission:{case_id}"
    assert events.channel_name(str(case_id)) == f"submission:{case_id}"


async def test_publish_status_sends_json_on_the_case_channel(fake_redis) -> None:
    case_id = uuid.uuid4()
    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(events.channel_name(case_id))

    await events.publish_status(case_id, "verifying", None, client=fake_redis)

    assert await _next_status(pubsub) == {"status": "verifying", "error": None}


async def test_publish_status_swallows_redis_errors() -> None:
    class BrokenRedis:
        async def publish(self, *_args):
            raise RedisConnectionError("down")

    await events.publish_status(uuid.uuid4(), "done", None, client=BrokenRedis())


async def test_set_status_publishes_after_commit(db_session, fake_redis) -> None:
    submission = await _submission(db_session)
    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(events.channel_name(submission.id))

    await orchestrator._set_status(db_session, submission, "scoring")

    assert await _next_status(pubsub) == {"status": "scoring", "error": None}


async def test_mark_failed_publishes_failed(
    db_session, db_session_factory, fake_redis, monkeypatch
) -> None:
    submission = await _submission(db_session, status="verifying")
    monkeypatch.setattr(orchestrator, "async_session_factory", db_session_factory)
    pubsub = fake_redis.pubsub()
    await pubsub.subscribe(events.channel_name(submission.id))

    await orchestrator._mark_failed(str(submission.id), "x")

    assert await _next_status(pubsub) == {"status": "failed", "error": "x"}


async def test_enqueue_failure_publishes_failed(
    app_client: AsyncClient, fake_redis, monkeypatch
) -> None:
    async def broken_enqueue(*_args) -> None:
        raise RedisConnectionError("queue down")

    published: list[tuple] = []

    async def record(submission_id, status, error, *, client=None) -> None:
        published.append((str(submission_id), status, error))

    monkeypatch.setattr(submissions_service, "enqueue", broken_enqueue)
    monkeypatch.setattr(submissions_service, "publish_status", record)
    await app_client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    await app_client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})

    resp = await app_client.post(
        "/submissions",
        json={"input_type": "text", "raw_input": "El cielo es azul."},
        headers={"X-CSRF-Token": app_client.cookies.get("csrf_token")},
    )

    assert resp.status_code == 503
    assert len(published) == 1
    assert published[0][1:] == ("failed", submissions_service.ENQUEUE_FAILURE)
