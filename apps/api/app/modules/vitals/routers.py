"""Requirement: INP. The web reports INP, LCP and CLS (plus FCP and TTFB)
with Next's useReportWebVitals (apps/web/components/web-vitals.tsx); this
endpoint writes each one to the log as a `web_vital` event, which lands in
Log Analytics (query in docs/AZURE.md#observabilidad).

No session and no CSRF token: metrics also come from signed-out visitors, and
navigator.sendBeacon can't add headers. That is safe because the endpoint has
no side effect besides one log line, and it is bounded instead: a 2 KB body
cap, a strict schema (fixed metric names, value ranges, no extra fields, a
route template rather than a URL) and a per-IP rate limit. The body is read
raw so text/plain works: that is what sendBeacon sends without a CORS
preflight.
"""

from typing import Annotated

import redis.asyncio as redis_asyncio
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.core.client_ip import client_ip
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.rate_limit import RateLimitExceeded, check_rate_limit, get_redis_dependency
from app.modules.vitals.schemas import VitalReport

settings = get_settings()
logger = get_logger(__name__)

router = APIRouter(tags=["vitals"])

MAX_BODY_BYTES = 2048


@router.post("/vitals", status_code=status.HTTP_204_NO_CONTENT)
async def report_vital(
    request: Request,
    redis_client: Annotated[redis_asyncio.Redis, Depends(get_redis_dependency)],
) -> Response:
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Cuerpo demasiado grande.")
    try:
        await check_rate_limit(
            f"vitals:ip:{client_ip(request)}",
            settings.rate_limit_vitals_per_minute,
            client=redis_client,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiadas métricas. Espera un momento.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc
    try:
        vital = VitalReport.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Métrica no válida.") from exc

    logger.info(
        "web_vital",
        name=vital.name,
        value=vital.value,
        rating=vital.rating,
        route=vital.route,
        navigation_type=vital.navigation_type,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
