import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

import evals.verdicts
from evals.verdicts.cases import load_cases

CASES_PATH = Path(evals.verdicts.__file__).parent / "cases.json"


def _case(case_id: str, kind: str = "false") -> dict:
    return {
        "id": case_id,
        "factchecker": "colombiacheck.com",
        "factcheck_url": "https://colombiacheck.com/chequeos/x",
        "factcheck_date": "2026-10-01",
        "rating": "Falso",
        "kind": kind,
        "claim": "Una afirmación.",
    }


def test_load_cases_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("a"), _case("a")]), encoding="utf-8")
    with pytest.raises(ValueError, match="a"):
        load_cases(path)


def test_load_cases_rejects_unknown_kind(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("a", kind="maybe")]), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_cases(path)


ORIGINAL_IDS = {
    "co-falso-1",
    "co-falso-2",
    "co-verdadero-1",
    "co-verdadero-2",
    "co-mixto-1",
    "co-mixto-2",
    "py-verdadero-1",
    "co-inventado-1",
}


def test_bundled_cases_file_is_valid() -> None:
    cases = load_cases(CASES_PATH)
    assert len(cases) == 20
    assert Counter(c.kind for c in cases) == {"false": 6, "true": 6, "mixed": 5, "invented": 3}


def test_original_cases_are_kept() -> None:
    assert {c.id for c in load_cases(CASES_PATH)} >= ORIGINAL_IDS


def test_new_verifiable_cases_have_coverage() -> None:
    for case in load_cases(CASES_PATH):
        if case.id not in ORIGINAL_IDS and case.kind != "invented":
            assert case.coverage_url, case.id
            assert case.coverage_url.startswith("https://"), case.id


def test_coverage_url_is_optional(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([_case("a")]), encoding="utf-8")
    assert load_cases(path)[0].coverage_url is None
