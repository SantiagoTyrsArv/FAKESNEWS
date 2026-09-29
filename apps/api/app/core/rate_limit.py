import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def get_redis_dependency() -> redis.Redis:
    """FastAPI dependency wrapper around get_redis(), so tests can override
    it via app.dependency_overrides without touching module globals.
    """
    return get_redis()


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded, retry after {retry_after_seconds}s")


async def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int = 60,
    client: redis.Redis | None = None,
) -> None:
    """Fixed-window rate limiter. Raises RateLimitExceeded when the window's
    request budget for `key` is used up.
    """
    r = client or get_redis()
    redis_key = f"ratelimit:{key}"

    current = await r.incr(redis_key)
    if current == 1:
        await r.expire(redis_key, window_seconds)

    if current > max_requests:
        ttl = await r.ttl(redis_key)
        raise RateLimitExceeded(retry_after_seconds=max(ttl, 1))
