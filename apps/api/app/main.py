from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import app.core.models_registry  # noqa: F401 - populates Base.metadata in this process
from app.core.config import get_settings
from app.core.db import engine
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import get_redis
from app.modules.auth.routers import router as auth_router
from app.modules.reports.routers import router as reports_router
from app.modules.sources.routers import router as sources_router
from app.modules.submissions.routers import router as submissions_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # Trusted-source seeding happens in the worker's startup hook (it's the
    # only process that actually needs sources populated before it can run
    # the verification pipeline) — not here, so this stays DB-independent
    # and safe to start without a live database (see tests/core/test_health.py).
    logger.info("app_startup", environment=settings.environment)
    yield
    await engine.dispose()
    redis_client = get_redis()
    await redis_client.aclose()
    logger.info("app_shutdown")


app = FastAPI(title="FakesNews API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)


app.include_router(auth_router)
app.include_router(submissions_router)
app.include_router(sources_router)
app.include_router(reports_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))

    redis_client = get_redis()
    await redis_client.ping()

    return {"status": "ready"}
