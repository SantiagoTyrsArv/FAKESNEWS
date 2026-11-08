from datetime import date
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.search import CREDITS_PER_SEARCH, SearchResult
from app.modules.pipeline import verify as verify_module
from app.modules.pipeline.verify import EvidenceItem, VerifyResult
from evals.verdicts.cases import Case
from evals.verdicts.runner import load_allowed_domains, run_cases

URL = "https://colombiacheck.com/chequeos/x"


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


@pytest.fixture(autouse=True)
def _fake_search(monkeypatch: pytest.MonkeyPatch) -> None:
    async def search(_query: str, _domains: list[str]) -> list[SearchResult]:
        return [SearchResult(result_id=1, url=URL, title="t", content="c", published_at=None)]

    monkeypatch.setattr(verify_module, "search_trusted", search)


def _fake_verify(verdict: str, *, fail_on: set[str] = frozenset()):
    """A stand-in for verify_claim that searches through the module, as the
    real one does, so the meter counts it."""

    async def verify(claim_text: str, *, allowed_domains: list[str]) -> VerifyResult:
        if any(case_id in claim_text for case_id in fail_on):
            raise RuntimeError("network down")
        await verify_module.search_trusted(claim_text, allowed_domains)
        evidence = [
            EvidenceItem(url=URL, domain="colombiacheck.com", snippet="...", stance="contradicts")
        ]
        return VerifyResult(verdict=verdict, rationale="porque sí", evidence=evidence)

    return verify


async def test_run_cases_grades_and_counts_credits() -> None:
    cases = [_case("c1", "false"), _case("c2", "true")]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_credits=40,
        verify=_fake_verify("CONTRADICTED"),
    )
    assert [r.grade for r in run.results] == ["ok", "severe"]
    assert run.results[0].contaminated is True
    assert run.results[0].credits == CREDITS_PER_SEARCH
    assert run.results[0].search_domains == ["colombiacheck.com"]
    assert run.spent_credits == 2 * CREDITS_PER_SEARCH
    assert run.skipped_case_ids == []


async def test_run_cases_stops_before_exceeding_budget() -> None:
    cases = [_case(f"c{i}", "false") for i in range(1, 5)]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_credits=2 * CREDITS_PER_SEARCH,
        verify=_fake_verify("CONTRADICTED"),
    )
    assert len(run.results) == 2
    assert run.skipped_case_ids == ["c3", "c4"]


async def test_run_cases_records_exception_and_continues() -> None:
    cases = [_case("c1", "false"), _case("c2", "false")]
    run = await run_cases(
        cases,
        allowed_domains=["colombiacheck.com"],
        max_credits=40,
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


async def test_run_cases_flags_a_failed_verification_as_error() -> None:
    async def failed(claim_text: str, *, allowed_domains: list[str]) -> VerifyResult:
        return VerifyResult(
            verdict="INSUFFICIENT",
            rationale="No se pudo completar.",
            evidence=[],
            verification_failed=True,
        )

    run = await run_cases(
        [_case("c1", "false")],
        allowed_domains=["colombiacheck.com"],
        max_credits=40,
        verify=failed,
    )
    assert run.results[0].grade == "error"
    assert "falló" in run.results[0].error


async def test_run_reports_the_model_in_use() -> None:
    run = await run_cases(
        [],
        allowed_domains=[],
        max_credits=40,
        verify=_fake_verify("CONTRADICTED"),
    )
    assert run.model == get_settings().gemini_model


def _recording_verify(seen: list[list[str]]):
    async def verify(claim_text: str, *, allowed_domains: list[str]) -> VerifyResult:
        seen.append(list(allowed_domains))
        return VerifyResult(verdict="INSUFFICIENT", rationale="", evidence=[])

    return verify


def _bbc_case(case_id: str) -> Case:
    return _case(case_id, "true").model_copy(update={"factchecker": "bbc.com"})


async def test_run_cases_blind_passes_reduced_domains_per_case() -> None:
    seen: list[list[str]] = []
    run = await run_cases(
        [_case("c1", "false"), _bbc_case("c2")],
        allowed_domains=["colombiacheck.com", "bbc.com", "eltiempo.com"],
        max_credits=40,
        verify=_recording_verify(seen),
        blind=True,
    )
    assert seen == [["bbc.com", "eltiempo.com"], ["eltiempo.com"]]
    assert run.blind is True


async def test_run_cases_not_blind_passes_all_domains() -> None:
    domains = ["colombiacheck.com", "bbc.com", "eltiempo.com"]
    seen: list[list[str]] = []
    run = await run_cases(
        [_case("c1", "false"), _bbc_case("c2")],
        allowed_domains=domains,
        max_credits=40,
        verify=_recording_verify(seen),
    )
    assert seen == [domains, domains]
    assert run.blind is False
