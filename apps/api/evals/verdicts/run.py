"""Run the verdict evaluation by hand. It spends real API credits from
the same key production uses: start with --dry-run.

    uv run python -m evals.verdicts.run --dry-run
    uv run python -m evals.verdicts.run --cases co-falso-1,co-verdadero-1
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from evals.verdicts import runner
from evals.verdicts.cases import load_cases
from evals.verdicts.report import render_report, usd

_HERE = Path(__file__).parent
CASES_PATH = _HERE / "cases.json"
RESULTS_DIR = _HERE / "results"
TRUSTED_SOURCES_PATH = _HERE.parents[1] / "app" / "data" / "trusted_sources.json"

DEFAULT_MAX_USD = 0.75
# The design's estimate for one claim, without a retry.
ESTIMATE_PER_CASE_USD = (0.06, 0.18)


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluación de veredictos (gasta créditos).")
    parser.add_argument("--cases", help="ids separados por comas; por defecto, todos")
    parser.add_argument("--max-usd", type=float, default=DEFAULT_MAX_USD)
    parser.add_argument("--dry-run", action="store_true", help="no llama a la API")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse(argv)
    cases = load_cases(CASES_PATH)
    if args.cases:
        wanted = [c.strip() for c in args.cases.split(",") if c.strip()]
        unknown = sorted(set(wanted) - {c.id for c in cases})
        if unknown:
            print(f"Casos desconocidos: {', '.join(unknown)}", file=sys.stderr)
            return 2
        cases = [c for c in cases if c.id in wanted]

    if args.dry_run:
        low, high = (len(cases) * x for x in ESTIMATE_PER_CASE_USD)
        for case in cases:
            print(f"- {case.id} ({case.rating}): {case.claim}")
        print(
            f"{len(cases)} casos; costo estimado {usd(low)}–{usd(high)}"
            f" ({usd(ESTIMATE_PER_CASE_USD[0])}–{usd(ESTIMATE_PER_CASE_USD[1])} por caso);"
            f" tope {usd(args.max_usd)}"
        )
        return 0

    if not get_settings().anthropic_api_key:
        # Without it every claim would silently come back INSUFFICIENT.
        print("Falta ANTHROPIC_API_KEY (en apps/api/.env o en el entorno).", file=sys.stderr)
        return 2

    run = asyncio.run(
        runner.run_cases(
            cases,
            allowed_domains=runner.load_allowed_domains(TRUSTED_SOURCES_PATH),
            max_usd=args.max_usd,
        )
    )
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem.with_suffix(".json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    report_path = stem.with_suffix(".md")
    report_path.write_text(render_report(run, {c.id: c for c in cases}), encoding="utf-8")
    print(f"Informe: {report_path}")
    print(f"Gasto estimado: {usd(run.spent_usd)} de {usd(args.max_usd)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
