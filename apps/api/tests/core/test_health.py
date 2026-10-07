from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import requires_integration


def test_health_liveness_returns_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@requires_integration
def test_health_ready_checks_db_and_redis() -> None:
    with TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_responses_carry_security_headers_and_request_id() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_untrusted_request_id_is_replaced() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "bad id\nwith newline"})

    assert response.headers["X-Request-ID"] != "bad id\nwith newline"
    assert len(response.headers["X-Request-ID"]) == 32


def test_unhandled_errors_return_generic_500() -> None:
    from fastapi import APIRouter

    router = APIRouter()

    @router.get("/__boom")
    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.include_router(router)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/__boom")
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__boom"]

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    assert response.headers["X-Request-ID"] in response.json()["detail"]
