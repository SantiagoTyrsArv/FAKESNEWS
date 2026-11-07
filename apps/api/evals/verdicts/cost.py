from collections.abc import Iterator
from contextlib import contextmanager

from app.core.search import CREDITS_PER_SEARCH
from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import verify as verify_module


class UsageMeter:
    """Adds up what the run used of the two free quotas."""

    def __init__(self) -> None:
        self.tavily_credits = 0
        self.gemini_calls = 0
        self.search_result_urls: list[str] = []


@contextmanager
def metering(meter: UsageMeter) -> Iterator[UsageMeter]:
    """Count every search and every Gemini call the pipeline makes, by
    wrapping the functions it calls, without changing what it does."""
    search = verify_module.search_trusted
    generators = [(m, m.generate_structured) for m in (verify_module, claims_module)]

    async def counted_search(query, domains):
        results = await search(query, domains)
        meter.tavily_credits += CREDITS_PER_SEARCH
        meter.search_result_urls.extend(r.url for r in results)
        return results

    def counted(generate):
        async def counted_generate(**kwargs):
            meter.gemini_calls += 1
            return await generate(**kwargs)

        return counted_generate

    verify_module.search_trusted = counted_search
    for module, generate in generators:
        module.generate_structured = counted(generate)
    try:
        yield meter
    finally:
        verify_module.search_trusted = search
        for module, generate in generators:
            module.generate_structured = generate


class BudgetGuard:
    """Stops the run before a case that could pass the credit cap."""

    def __init__(self, max_credits: int) -> None:
        self.max_credits = max_credits

    def can_start(self, spent_credits: int) -> bool:
        return spent_credits + CREDITS_PER_SEARCH <= self.max_credits
