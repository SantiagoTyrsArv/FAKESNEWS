"""Case progress events over Redis pub/sub.

Requirement: WebSockets. The pipeline runs in the worker, the WebSocket lives
in the API (another container): every status change is published on
`submission:{id}`, and app/modules/submissions/live.py forwards it to the
browser. Publishing is best effort: if Redis fails, the pipeline carries on
and the report page's polling fallback still sees the new status.
"""

import json
import uuid

import redis.asyncio as redis
from redis.exceptions import RedisError

from app.core.logging import get_logger
from app.core.rate_limit import get_redis

logger = get_logger(__name__)


def channel_name(submission_id: uuid.UUID | str) -> str:
    return f"submission:{submission_id}"


async def publish_status(
    submission_id: uuid.UUID | str,
    status: str,
    error: str | None,
    *,
    client: redis.Redis | None = None,
) -> None:
    payload = json.dumps({"status": status, "error": error})
    try:
        await (client or get_redis()).publish(channel_name(submission_id), payload)
    except (RedisError, OSError) as exc:
        logger.warning(
            "submission_event_publish_failed", submission_id=str(submission_id), error=str(exc)
        )
