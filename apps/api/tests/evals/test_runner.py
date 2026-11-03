from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.modules.pipeline import verify as verify_module
from app.modules.pipeline.verify import EvidenceItem, VerifyResult
from evals.verdicts.cases import Case
from evals.verdicts.runner import load_allowed_domains, run_cases


def _case(case_id: str, kind: str) -> Case:
    return Case(
        id=case_id,
        factchecker="colombiacheck.com",
        factcheck_url=f"https://colombiacheck.com/chequeos/{case_id}",
        factcheck_date=date(2026, 10, 1),
        rating="Falso",
        kind=kind,
        claim=f"Afirmación {case_id}.",
    )


def _fake_verify(verdict: str, *, input_tokens: int = 100_000, fail_on: set[str] = frozenset()):
    """A stand-in for verify_claim that reports usage through log_usage, as
    the real one does, so the meter counts it. 100k input tokens = 0.20 USD,
    plus 10 searches = 0.10 USD: 0.30 USD per call."""
    url = "https://colombiacheck.com/chequeos/x"

    async def verify(claim_text: str, *, allowed_domains: list[str]) -> VerifyResult:
        if any(case_id in claim_text for case_id in fail_on):
            raise RuntimeError("network down")
        content = [
            SimpleNamespace(
                type="web_search_tool_result",
                content=[SimpleNamespace(type="web_search_result", url=url)],
            )
        ]
        usage = SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=0,
            server_tool_use=SimpleNamespace(web_search_requests=10),
        )
        verify_module.log_usage(
            "verify", SimpleNamespace(content=content, usage=usage, stop_reason="end_turn")
        )
        evidence = [
            EvidenceItem(url=url, domain="colombiacheck.com", snippet="...", stance="contradicts")
        ]
        return VerifyResult(verdict=verdict, rationale="porque sí", evidence=evidence)

    return verify


async def test_run_cases_grades_and_costs() -> None:
    cases = [_case("c1", "false"), _case("c2", "true")]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_usd=5.0,
        verify=_fake_verify("CONTRADICTED"),
    )
    assert [r.grade for r in run.results] == ["ok", "severe"]
    assert run.results[0].contaminated is True
    assert run.results[0].cost_usd == pytest.approx(0.30)
    assert run.results[0].search_domains == ["colombiacheck.com"]
    assert run.spent_usd == pytest.approx(sum(r.cost_usd for r in run.results))
    assert run.skipped_case_ids == []


async def test_run_cases_stops_before_exceeding_budget() -> None:
    cases = [_case(f"c{i}", "false") for i in range(1, 5)]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_usd=0.75,
        verify=_fake_verify("CONTRADICTED"),
    )
    assert len(run.results) == 2
    assert run.skipped_case_ids == ["c3", "c4"]
    assert run.spent_usd <= 0.75


async def test_run_cases_records_exception_and_continues() -> None:
    cases = [_case("c1", "false"), _case("c2", "false")]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_usd=5.0,
        verify=_fake_verify("CONTRADICTED", fail_on={"c1"}),
    )
    assert run.results[0].grade == "error"
    assert run.results[0].got is None
    assert run.results[0].error == "network down"
    assert run.results[1].grade == "ok"


def test_load_allowed_domains_reads_trusted_sources() -> None:
    domains = load_allowed_domains(Path("app/data/trusted_sources.json"))
    assert "colombiacheck.com" in domains
    assert len(domains) == 25
