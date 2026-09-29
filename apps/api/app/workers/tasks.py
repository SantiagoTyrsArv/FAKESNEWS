from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


async def ping(_ctx: dict[str, Any]) -> str:
    """Trivial task used to verify the worker is wired up end-to-end."""
    logger.info("worker_ping")
    return "pong"
