from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import verify as verify_module

# Official first-party prices for claude-sonnet-5 on PRICES_AS_OF.
PRICES_AS_OF = "2026-11-03"
INPUT_USD_PER_MTOK = 2.0
OUTPUT_USD_PER_MTOK = 10.0
WEB_SEARCH_USD = 0.01

# Before any case has run there is no measured cost to go by: the design's
# upper estimate for one claim, retry included.
FIRST_CASE_ESTIMATE_USD = 0.35


def call_cost(input_tokens: int, output_tokens: int, web_searches: int) -> float:
    return (
        input_tokens * INPUT_USD_PER_MTOK / 1_000_000
        + output_tokens * OUTPUT_USD_PER_MTOK / 1_000_000
        + web_searches * WEB_SEARCH_USD
    )


class UsageMeter:
    """Adds up what every API response reports it used."""

    def __init__(self) -> None:
        self.input_tokens = 0
        self.output_tokens = 0
        self.web_searches = 0
        self.search_result_urls: list[str] = []

    @property
    def spent_usd(self) -> float:
        return call_cost(self.input_tokens, self.output_tokens, self.web_searches)

    def record(self, response: Any) -> None:
        usage = response.usage
        self.input_tokens += usage.input_tokens
        self.output_tokens += usage.output_tokens
        if usage.server_tool_use is not None:
            self.web_searches += usage.server_tool_use.web_search_requests
        for block in response.content:
            if getattr(block, "type", None) != "web_search_tool_result":
                continue
            if not isinstance(block.content, list):
                continue  # an error object, not a results list
            self.search_result_urls.extend(
                item.url
                for item in block.content
                if getattr(item, "type", None) == "web_search_result"
            )


@contextmanager
def metering(meter: UsageMeter) -> Iterator[UsageMeter]:
    """Feed every response the pipeline logs to `meter` as well. The
    pipeline already calls log_usage once per API response, so wrapping it
    reads the usage without changing what the pipeline does."""
    modules = (verify_module, claims_module)
    originals = [module.log_usage for module in modules]

    def wrap(original):
        def log_and_record(step: str, response: Any) -> None:
            original(step, response)
            meter.record(response)

        return log_and_record

    for module, original in zip(modules, originals, strict=True):
        module.log_usage = wrap(original)
    try:
        yield meter
    finally:
        for module, original in zip(modules, originals, strict=True):
            module.log_usage = original


class BudgetGuard:
    def __init__(self, max_usd: float) -> None:
        self.max_usd = max_usd

    def can_start(self, spent_usd: float, largest_case_usd: float) -> bool:
        """Whether one more case fits, assuming it costs as much as the most
        expensive case so far."""
        next_case = largest_case_usd or FIRST_CASE_ESTIMATE_USD
        return spent_usd + next_case <= self.max_usd
