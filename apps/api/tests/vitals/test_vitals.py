import json

from httpx import AsyncClient
from structlog.testing import capture_logs

from app.modules.vitals import routers as vitals_routers

VALID = {
    "name": "INP",
    "value": 184.0,
    "rating": "good",
    "id": "v5-1731111111111-1234567890",
    "navigation_type": "navigate",
    "route": "/reports/[id]",
}


async def _post(client: AsyncClient, body: dict | str) -> int:
    content = body if isinstance(body, str) else json.dumps(body)
    resp = await client.post("/vitals", content=content, headers={"content-type": "text/plain"})
    return resp.status_code


def _vital_logs(logs: list[dict]) -> list[dict]:
    return [entry for entry in logs if entry.get("event") == "web_vital"]


async def test_vital_is_logged(app_client: AsyncClient) -> None:
    with capture_logs() as logs:
        code = await _post(app_client, VALID)

    assert code == 204
    (entry,) = _vital_logs(logs)
    assert entry["name"] == "INP"
    assert entry["value"] == 184.0
    assert entry["rating"] == "good"
    assert entry["route"] == "/reports/[id]"
    assert entry["log_level"] == "info"


async def test_vital_accepts_json_content_type_too(app_client: AsyncClient) -> None:
    resp = await app_client.post("/vitals", json=VALID)
    assert resp.status_code == 204


async def test_vital_rejects_unknown_metric(app_client: AsyncClient) -> None:
    with capture_logs() as logs:
        code = await _post(app_client, {**VALID, "name": "FID"})

    assert code == 422
    assert _vital_logs(logs) == []


async def test_vital_rejects_a_real_report_url(app_client: AsyncClient) -> None:
    code = await _post(app_client, {**VALID, "route": "/reports/9f0c?x=1"})
    assert code == 422


async def test_vital_rejects_extra_fields(app_client: AsyncClient) -> None:
    code = await _post(app_client, {**VALID, "email": "a@b.c"})
    assert code == 422


async def test_vital_rejects_out_of_range_values(app_client: AsyncClient) -> None:
    assert await _post(app_client, {**VALID, "value": -1}) == 422
    assert await _post(app_client, {**VALID, "value": 10_000_000}) == 422


async def test_vital_rejects_malformed_json(app_client: AsyncClient) -> None:
    assert await _post(app_client, "{not json") == 422


async def test_vital_rejects_oversized_body(app_client: AsyncClient) -> None:
    with capture_logs() as logs:
        code = await _post(app_client, {**VALID, "id": "x" * 3000})

    assert code == 413
    assert _vital_logs(logs) == []


async def test_vitals_are_rate_limited(app_client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(vitals_routers.settings, "rate_limit_vitals_per_minute", 2)

    codes = [await _post(app_client, VALID) for _ in range(3)]

    assert codes == [204, 204, 429]


async def test_rate_limit_applies_before_reading_the_body(
    app_client: AsyncClient, monkeypatch
) -> None:
    # An anonymous endpoint must not read large bodies for an IP that is
    # already over its budget.
    monkeypatch.setattr(vitals_routers.settings, "rate_limit_vitals_per_minute", 2)
    big = {**VALID, "id": "x" * 3000}

    codes = [await _post(app_client, big) for _ in range(3)]

    assert codes == [413, 413, 429]


async def test_oversized_chunked_body_is_rejected(app_client: AsyncClient) -> None:
    async def chunks():
        for _ in range(64):
            yield b"x" * 1024

    resp = await app_client.post(
        "/vitals", content=chunks(), headers={"content-type": "text/plain"}
    )

    assert resp.status_code == 413


async def test_declared_content_length_over_the_cap_is_rejected(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/vitals",
        content=json.dumps(VALID),
        headers={"content-type": "text/plain", "content-length": "999999"},
    )

    assert resp.status_code == 413
