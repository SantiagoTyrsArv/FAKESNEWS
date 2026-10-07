"""Cross-cutting HTTP concerns, applied to every request in one place.

- Request IDs: each request gets an id (or keeps a sane incoming
  X-Request-ID), bound into every log line and echoed back in the response,
  so a user-visible error can be traced to its logs.
- Security headers: the API only serves JSON, so it can forbid framing,
  sniffing and any active content outright, and must not be cached by
  shared caches since responses carry per-user data.
- Unhandled errors: logged with the request id and answered with a generic
  500, never with the exception text (which can leak internals).
"""

import re
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# Public, non-personal endpoints that shared caches may store briefly.
_CACHEABLE_PREFIXES = ("/sources",)

_BASE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

# JSON needs no scripts, styles or frames. The interactive docs (dev only) do,
# so they're exempt.
_API_CSP = "default-src 'none'; frame-ancestors 'none'"
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _request_id(request: Request) -> str:
    incoming = request.headers.get(REQUEST_ID_HEADER, "")
    return incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex


def _apply_security_headers(request: Request, response: Response) -> None:
    for name, value in _BASE_SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)

    path = request.url.path
    if not path.startswith(_DOCS_PATHS):
        response.headers.setdefault("Content-Security-Policy", _API_CSP)

    if request.method == "GET" and path.startswith(_CACHEABLE_PREFIXES):
        response.headers.setdefault("Cache-Control", "public, max-age=60")
    else:
        response.headers.setdefault("Cache-Control", "no-store")

    if get_settings().is_production:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )


def install_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _request_id(request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_error", method=request.method, path=request.url.path)
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "Error interno del servidor. Si persiste, comparte este código "
                    f"con soporte: {request_id}",
                },
            )

        _apply_security_headers(request, response)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return response
