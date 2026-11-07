import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from evals.verdicts import run as run_module
from evals.verdicts import runner
from evals.verdicts.runner import RunResult

CASE = {
    "id": "co-falso-1",
    "factchecker": "colombiacheck.com",
    "factcheck_url": "https://colombiacheck.com/chequeos/x",
    "factcheck_date": "2026-10-01",
    "rating": "Falso",
    "kind": "false",
    "claim": "Una afirmación.",
}


@pytest.fixture
def cases_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([CASE]), encoding="utf-8")
    monkeypatch.setattr(run_module, "CASES_PATH", path)
    monkeypatch.setattr(run_module, "RESULTS_DIR", tmp_path / "results")
    return path


def _forbid_api(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args, **_kwargs):
        raise AssertionError("must not run cases")

    monkeypatch.setattr(runner, "run_cases", fail)


def _with_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setattr(run_module.get_settings(), "gemini_api_key", key)
    monkeypatch.setattr(run_module.get_settings(), "tavily_api_key", key)


def test_unknown_case_id_exits_2_without_calling_api(cases_file, monkeypatch, capsys) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "sk-test")
    assert run_module.main(["--cases", "nope"]) == 2
    assert "nope" in capsys.readouterr().err


def test_missing_api_key_exits_2(cases_file, monkeypatch, capsys) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "")
    assert run_module.main([]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err


def test_dry_run_prints_cases_and_estimate_without_calling_api(
    cases_file, monkeypatch, capsys
) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "")
    assert run_module.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "co-falso-1" in out
    assert "2 créditos" in out


def test_run_writes_json_and_report(cases_file, monkeypatch, tmp_path) -> None:
    _with_key(monkeypatch, "sk-test")

    async def fake_run_cases(cases, *, allowed_domains, max_credits):
        assert "colombiacheck.com" in allowed_domains
        return RunResult(
            started_at=datetime(2026, 11, 3, tzinfo=UTC),
            model="gemini-test",
            max_credits=max_credits,
            results=[],
            skipped_case_ids=[],
            spent_credits=0,
        )

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)
    assert run_module.main(["--max-credits", "4"]) == 0
    files = sorted(p.suffix for p in (tmp_path / "results").iterdir())
    assert files == [".json", ".md"]


def test_production_model_reads_the_bicep_parameters() -> None:
    assert run_module.production_model() == "gemini-3.5-flash-lite"


def test_production_model_tolerates_a_missing_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(run_module, "BICEP_PARAMS_PATH", tmp_path / "nada.bicepparam")

    assert run_module.production_model() is None


def test_run_warns_when_model_differs_from_production(cases_file, monkeypatch, capsys) -> None:
    _with_key(monkeypatch, "k")
    monkeypatch.setattr(run_module.get_settings(), "gemini_model", "otro-modelo")

    async def fake_run_cases(cases, *, allowed_domains, max_credits):
        return RunResult(
            started_at=datetime(2026, 11, 3, tzinfo=UTC),
            model="otro-modelo",
            max_credits=max_credits,
            results=[],
            skipped_case_ids=[],
            spent_credits=0,
        )

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)
    monkeypatch.setattr(run_module, "production_model", lambda: "gemini-prod")

    assert run_module.main([]) == 0
    assert "no es el modelo de producción" in capsys.readouterr().err
