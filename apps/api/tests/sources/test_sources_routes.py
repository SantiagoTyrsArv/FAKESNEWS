import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import Source, SourceScoreEvent


async def _seed_source(db_session: AsyncSession, **overrides) -> Source:
    defaults = dict(domain="reuters.com", name="Reuters", type="agencia", alpha=8.0, beta=2.0)
    defaults.update(overrides)
    source = Source(**defaults)
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    return source


async def test_list_sources_is_public_and_includes_score(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_source(db_session)

    resp = await app_client.get("/sources")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["sources"]) == 1
    entry = body["sources"][0]
    assert entry["domain"] == "reuters.com"
    assert entry["score"] == 0.8
    assert entry["low_sample"] is True  # cases_count defaults to 0


async def test_get_source_detail_includes_interval_and_events(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    source = await _seed_source(db_session, cases_count=12)
    claim_id = uuid.uuid4()
    db_session.add(SourceScoreEvent(source_id=source.id, claim_id=claim_id, outcome="hit"))
    await db_session.commit()

    resp = await app_client.get(f"/sources/{source.domain}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["domain"] == "reuters.com"
    assert body["low_sample"] is False
    assert 0.0 <= body["score_interval_low"] <= body["score"] <= body["score_interval_high"] <= 1.0
    assert len(body["recent_events"]) == 1
    assert body["recent_events"][0]["outcome"] == "hit"
    assert body["recent_events"][0]["claim_id"] == str(claim_id)


async def test_get_source_detail_accepts_url_and_strips_www(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_source(db_session, domain="elpais.com")

    resp = await app_client.get("/sources/www.elpais.com")

    assert resp.status_code == 200
    assert resp.json()["domain"] == "elpais.com"


async def test_get_source_not_found(app_client: AsyncClient) -> None:
    resp = await app_client.get("/sources/does-not-exist.example")

    assert resp.status_code == 404
