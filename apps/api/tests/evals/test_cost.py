import pytest

from app.core.search import CREDITS_PER_SEARCH, SearchResult
from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import verify as verify_module
from evals.verdicts.cost import BudgetGuard, UsageMeter, metering


def _result(url: str = "https://a.com/1") -> SearchResult:
    return SearchResult(result_id=1, url=url, title="t", content="c", published_at=None)


@pytest.fixture
def fake_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    async def search(_query: str, _domains: list[str]) -> list[SearchResult]:
        return [_result()]

    async def generate(**_kwargs) -> str:
        return "respuesta"

    monkeypatch.setattr(verify_module, "search_trusted", search)
    monkeypatch.setattr(verify_module, "generate_structured", generate)
    monkeypatch.setattr(claims_module, "generate_structured", generate)


@pytest.mark.usefixtures("fake_providers")
async def test_metering_counts_searches_and_gemini_calls() -> None:
    meter = UsageMeter()

    with metering(meter):
        await verify_module.search_trusted("q", ["a.com"])
        await verify_module.generate_structured(step="verify")
        await claims_module.generate_structured(step="claims")

    assert meter.tavily_credits == CREDITS_PER_SEARCH
    assert meter.gemini_calls == 2
    assert meter.search_result_urls == ["https://a.com/1"]


@pytest.mark.usefixtures("fake_providers")
async def test_metering_returns_what_the_provider_returned() -> None:
    with metering(UsageMeter()):
        assert await verify_module.generate_structured(step="verify") == "respuesta"


@pytest.mark.usefixtures("fake_providers")
async def test_metering_restores_the_functions() -> None:
    original = verify_module.search_trusted

    with metering(UsageMeter()):
        assert verify_module.search_trusted is not original

    assert verify_module.search_trusted is original


@pytest.mark.usefixtures("fake_providers")
def test_metering_restores_on_exception() -> None:
    original = verify_module.search_trusted

    with pytest.raises(RuntimeError), metering(UsageMeter()):
        raise RuntimeError("boom")

    assert verify_module.search_trusted is original


def test_budget_guard_stops_at_max_credits() -> None:
    assert BudgetGuard(2).can_start(spent_credits=2) is False


def test_budget_guard_allows_a_case_that_fits() -> None:
    assert BudgetGuard(4).can_start(spent_credits=2) is True
