from datetime import UTC, date, datetime

from evals.verdicts.cases import Case
from evals.verdicts.report import render_report
from evals.verdicts.runner import CaseResult, RunResult


def _case(case_id: str, kind: str) -> Case:
    return Case(
        id=case_id,
        factchecker="colombiacheck.com",
        factcheck_url=f"https://colombiacheck.com/chequeos/{case_id}",
        factcheck_date=date(2026, 10, 1),
        rating="Falso" if kind == "false" else "Verdadero",
        kind=kind,
        claim=f"Afirmación {case_id}.",
    )


def _result(case_id: str, kind: str, got: str | None, grade: str, *, contaminated=False):
    evidence = [
        {
            "url": "https://colombiacheck.com/x",
            "domain": "colombiacheck.com",
            "stance": "contradicts",
        }
    ]
    return CaseResult(
        case_id=case_id,
        kind=kind,
        rating="Falso",
        got=got,
        grade=grade,
        rationale=f"Explicación de {case_id}.",
        evidence=evidence if contaminated else [],
        contaminated=contaminated,
        search_domains=["colombiacheck.com"],
        cost_usd=0.1,
        input_tokens=1000,
        output_tokens=100,
        web_searches=2,
    )


def _run(results, skipped=()):
    return RunResult(
        started_at=datetime(2026, 11, 3, tzinfo=UTC),
        model="claude-sonnet-5",
        max_usd=0.75,
        prices_as_of="2026-11-03",
        results=results,
        skipped_case_ids=list(skipped),
        spent_usd=sum(r.cost_usd for r in results),
    )


def test_report_marks_severe_and_contaminated() -> None:
    cases = {"c1": _case("c1", "false"), "c2": _case("c2", "true")}
    run = _run(
        [
            _result("c1", "false", "CONTRADICTED", "ok", contaminated=True),
            _result("c2", "true", "CONTRADICTED", "severe"),
        ]
    )
    md = render_report(run, cases)
    assert "✗ grave" in md
    assert "| sí |" in md
    assert "2 USD" in md
    assert "10 USD" in md
    assert "0,01 USD" in md
    assert "0,75 USD" in md
    assert "Explicación de c1." in md
    assert "https://colombiacheck.com/chequeos/c1" in md


def test_report_score_without_contaminated() -> None:
    cases = {c: _case(c, "false") for c in ("c1", "c2", "c3")}
    run = _run(
        [
            _result("c1", "false", "CONTRADICTED", "ok", contaminated=True),
            _result("c2", "false", "CONTRADICTED", "ok"),
            _result("c3", "false", "INSUFFICIENT", "fail"),
        ]
    )
    md = render_report(run, cases)
    assert "2 de 3" in md
    assert "1 de 2" in md


def test_report_lists_skipped_cases() -> None:
    cases = {c: _case(c, "false") for c in ("c1", "c2")}
    run = _run([_result("c1", "false", "CONTRADICTED", "ok")], skipped=["c2"])
    md = render_report(run, cases)
    assert "c2" in md.split("tope")[-1]
