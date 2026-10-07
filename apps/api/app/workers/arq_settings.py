from typing import Any

from arq.connections import RedisSettings

import app.core.models_registry  # noqa: F401 - populates Base.metadata in this process
from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.modules.pipeline.orchestrator import run_pipeline
from app.modules.sources.seed_loader import load_trusted_sources
from app.workers.tasks import ping

settings = get_settings()
logger = get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(settings.log_level)
    async with async_session_factory() as db:
        await load_trusted_sources(db)
    logger.info("worker_startup")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker_shutdown")


class WorkerSettings:
    functions = [ping, run_pipeline]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = settings.pipeline_job_timeout_seconds
