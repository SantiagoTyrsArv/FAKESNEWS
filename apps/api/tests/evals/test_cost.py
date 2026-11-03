import json
from types import SimpleNamespace

import pytest

from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import verify as verify_module
from evals.verdicts.cost import BudgetGuard, UsageMeter, call_cost, metering


def _response(*, content=(), input_tokens=0, output_tokens=0, web_searches=None):
    server_tool_use = (
        None if web_searches is None else SimpleNamespace(web_search_requests=web_searches)
    )
    usage = SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens, server_tool_use=server_tool_use
    )
    return SimpleNamespace(content=list(content), stop_reason="end_turn", usage=usage)


def _search_block(content):
    return SimpleNamespace(type="web_search_tool_result", content=content)


def _result(url: str):
    return SimpleNamespace(type="web_search_result", url=url, page_age=None)


def test_call_cost() -> None:
    assert call_cost(1_000_000, 0, 0) == pytest.approx(2.0)
    assert call_cost(0, 1_000_000, 0) == pytest.approx(10.0)
    assert call_cost(0, 0, 3) == pytest.approx(0.03)


def test_meter_handles_missing_server_tool_use() -> None:
    meter = UsageMeter()
    meter.record(_response(input_tokens=1000, output_tokens=100))
    assert meter.web_searches == 0
    assert meter.spent_usd == pytest.approx(call_cost(1000, 100, 0))


def test_meter_collects_search_result_urls() -> None:
    meter = UsageMeter()
    error = SimpleNamespace(type="web_search_tool_result_error", error_code="unavailable")
    meter.record(
        _response(
            content=[_search_block([_result("https://a.com/1")]), _search_block(error)],
            web_searches=2,
        )
    )
    assert meter.search_result_urls == ["https://a.com/1"]
    assert meter.web_searches == 2


async def test_metering_records_verify_calls_and_restores(monkeypatch) -> None:
    url = "https://reuters.com/a"
    answer = {
        "verdict": "SUPPORTED",
        "rationale": "...",
        "evidence": [{"url": url, "snippet": "...", "stance": "supports"}],
    }
    response = _response(
        content=[
            _search_block([_result(url)]),
            SimpleNamespace(type="text", text=json.dumps(answer)),
        ],
        input_tokens=500,
        output_tokens=50,
        web_searches=2,
    )

    async def create(**_kwargs):
        return response

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    monkeypatch.setattr(verify_module, "get_anthropic_client", lambda: client)
    original_verify_log, original_claims_log = verify_module.log_usage, claims_module.log_usage

    meter = UsageMeter()
    with metering(meter):
        await verify_module.verify_claim("afirmación", allowed_domains=["reuters.com"])

    assert meter.web_searches == 2
    assert meter.input_tokens == 500
    assert verify_module.log_usage is original_verify_log
    assert claims_module.log_usage is original_claims_log


def test_metering_restores_on_exception() -> None:
    original = verify_module.log_usage
    with pytest.raises(RuntimeError), metering(UsageMeter()):
        raise RuntimeError("boom")
    assert verify_module.log_usage is original


def test_budget_guard() -> None:
    guard = BudgetGuard(0.75)
    assert guard.can_start(0.0, 0.0)  # 0 + 0.35 <= 0.75
    assert guard.can_start(0.40, 0.30)  # 0.70
    assert not guard.can_start(0.50, 0.30)  # 0.80 > 0.75
