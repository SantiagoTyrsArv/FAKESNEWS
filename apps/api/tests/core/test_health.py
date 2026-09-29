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
