"""Web search restricted to the trusted sources, through Tavily."""

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

SEARCH_URL = "https://api.tavily.com/search"
SEARCH_DEPTH = "advanced"
CREDITS_PER_SEARCH = 2
MAX_RESULTS = 8
MAX_QUERY_CHARS = 400
TIMEOUT_SECONDS = 10
RETRY_WAIT_SECONDS = 1
# Tavily's codes for a used-up plan and a used-up pay-as-you-go limit.
QUOTA_STATUSES = frozenset({432, 433})
RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})


class SearchError(Exception):
    pass


class SearchQuotaError(SearchError):
    pass


@dataclass(frozen=True)
class SearchResult:
    result_id: int
    url: str
    title: str
    content: str
    published_at: str | None


async def _post(payload: dict) -> httpx.Response:
    headers = {"Authorization": f"Bearer {settings.tavily_api_key}"}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        return await client.post(SEARCH_URL, json=payload, headers=headers)


async def search_trusted(query: str, domains: list[str]) -> list[SearchResult]:
    payload = {
        "query": query[:MAX_QUERY_CHARS],
        "search_depth": SEARCH_DEPTH,
        "max_results": MAX_RESULTS,
        "include_domains": domains,
        "include_published_date": True,
    }
    error = "sin respuesta"
    for attempt in range(2):
        if attempt:
            await asyncio.sleep(RETRY_WAIT_SECONDS)
        try:
            response = await _post(payload)
        except httpx.HTTPError as exc:
            error = type(exc).__name__
            continue

        if response.status_code in QUOTA_STATUSES:
            logger.error("search_quota_exhausted", status=response.status_code)
            raise SearchQuotaError(f"Tavily respondió {response.status_code}")
        if response.status_code in RETRYABLE_STATUSES:
            error = f"Tavily respondió {response.status_code}"
            continue
        if response.status_code != 200:
            raise SearchError(f"Tavily respondió {response.status_code}")

        results = [
            SearchResult(
                result_id=index,
                url=item["url"],
                title=item.get("title") or "",
                content=item.get("content") or "",
                published_at=item.get("published_date"),
            )
            for index, item in enumerate(response.json().get("results", []), start=1)
        ]
        logger.info("search_usage", credits=CREDITS_PER_SEARCH, results=len(results))
        return results

    raise SearchError(error)
