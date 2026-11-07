import json
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


def test_bundled_cases_file_is_valid() -> None:
    cases = load_cases(CASES_PATH)
    assert len(cases) == 8
    assert sorted(c.kind for c in cases) == [
        "false",
        "false",
        "invented",
        "mixed",
        "mixed",
        "true",
        "true",
        "true",
    ]
