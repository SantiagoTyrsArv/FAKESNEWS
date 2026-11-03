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
    monkeypatch.setattr(run_module.get_settings(), "anthropic_api_key", key)


def test_unknown_case_id_exits_2_without_calling_api(cases_file, monkeypatch, capsys) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "sk-test")
    assert run_module.main(["--cases", "nope"]) == 2
    assert "nope" in capsys.readouterr().err


def test_missing_api_key_exits_2(cases_file, monkeypatch, capsys) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "")
    assert run_module.main([]) == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_dry_run_prints_cases_and_estimate_without_calling_api(
    cases_file, monkeypatch, capsys
) -> None:
    _forbid_api(monkeypatch)
    _with_key(monkeypatch, "")
    assert run_module.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "co-falso-1" in out
    assert "estimado" in out and "0,06" in out and "0,18" in out


def test_run_writes_json_and_report(cases_file, monkeypatch, tmp_path) -> None:
    _with_key(monkeypatch, "sk-test")

    async def fake_run_cases(cases, *, allowed_domains, max_usd):
        assert "colombiacheck.com" in allowed_domains
        return RunResult(
            started_at=datetime(2026, 11, 3, tzinfo=UTC),
            model="claude-sonnet-5",
            max_usd=max_usd,
            prices_as_of="2026-11-03",
            results=[],
            skipped_case_ids=[],
            spent_usd=0.0,
        )

    monkeypatch.setattr(runner, "run_cases", fake_run_cases)
    assert run_module.main(["--max-usd", "0.5"]) == 0
    files = sorted(p.suffix for p in (tmp_path / "results").iterdir())
    assert files == [".json", ".md"]
