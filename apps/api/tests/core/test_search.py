import json

import httpx
import pytest
import respx

from app.core import search
from app.core.search import SearchError, SearchQuotaError, search_trusted

URL = "https://api.tavily.com/search"


def _ok(*results: dict) -> httpx.Response:
    return httpx.Response(200, json={"results": list(results)})


def _result(url: str = "https://a.com/1", date: str | None = "2026-11-03") -> dict:
    return {"url": url, "title": "Título", "content": "Fragmento", "published_date": date}


@pytest.fixture(autouse=True)
def _settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search.settings, "tavily_api_key", "tvly-secret")
    monkeypatch.setattr(search, "RETRY_WAIT_SECONDS", 0)


@respx.mock
async def test_search_sends_the_agreed_request() -> None:
    route = respx.post(URL).mock(return_value=_ok())

    await search_trusted("consulta", ["a.com"])

    request = route.calls.last.request
    body = json.loads(request.content)
    assert request.headers["Authorization"] == "Bearer tvly-secret"
    assert body["query"] == "consulta"
    assert body["include_domains"] == ["a.com"]
    assert body["max_results"] == 8
    assert body["search_depth"] == "advanced"
    assert body["include_published_date"] is True


@respx.mock
async def test_search_numbers_results_from_one() -> None:
    respx.post(URL).mock(return_value=_ok(_result("https://a.com/1"), _result("https://a.com/2")))

    results = await search_trusted("q", ["a.com"])

    assert [r.result_id for r in results] == [1, 2]
    assert results[0].url == "https://a.com/1"
    assert results[0].content == "Fragmento"
    assert results[0].published_at == "2026-11-03"


@respx.mock
async def test_search_accepts_results_without_a_date() -> None:
    respx.post(URL).mock(return_value=_ok(_result(date=None)))

    assert (await search_trusted("q", ["a.com"]))[0].published_at is None


@respx.mock
async def test_search_truncates_long_queries() -> None:
    route = respx.post(URL).mock(return_value=_ok())

    await search_trusted("x" * 900, ["a.com"])

    assert len(json.loads(route.calls.last.request.content)["query"]) == search.MAX_QUERY_CHARS


@pytest.mark.parametrize("status", [432, 433])
@respx.mock
async def test_search_quota_raises_search_quota_error(status: int) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(status))

    with pytest.raises(SearchQuotaError):
        await search_trusted("q", ["a.com"])

    assert route.call_count == 1


@respx.mock
async def test_search_retries_once_on_a_server_error() -> None:
    route = respx.post(URL).mock(side_effect=[httpx.Response(502), _ok(_result())])

    assert len(await search_trusted("q", ["a.com"])) == 1
    assert route.call_count == 2


@respx.mock
async def test_search_gives_up_after_one_retry() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(503))

    with pytest.raises(SearchError):
        await search_trusted("q", ["a.com"])

    assert route.call_count == 2


@respx.mock
async def test_search_client_errors_are_not_retried() -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(400))

    with pytest.raises(SearchError):
        await search_trusted("q", ["a.com"])

    assert route.call_count == 1


@respx.mock
async def test_search_errors_never_contain_the_api_key() -> None:
    respx.post(URL).mock(return_value=httpx.Response(401, text="tvly-secret"))

    with pytest.raises(SearchError) as exc:
        await search_trusted("q", ["a.com"])

    assert "tvly-secret" not in str(exc.value)
