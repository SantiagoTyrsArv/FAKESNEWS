"""Run the verdict evaluation by hand. It uses the free quotas production
relies on, so it never runs in CI: start with --dry-run.

    uv run python -m evals.verdicts.run --dry-run
    uv run python -m evals.verdicts.run --cases co-falso-1,co-verdadero-1
"""

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.search import CREDITS_PER_SEARCH
from evals.verdicts import runner
from evals.verdicts.cases import load_cases
from evals.verdicts.report import render_report

_HERE = Path(__file__).parent
CASES_PATH = _HERE / "cases.json"
RESULTS_DIR = _HERE / "results"
TRUSTED_SOURCES_PATH = _HERE.parents[1] / "app" / "data" / "trusted_sources.json"

BICEP_PARAMS_PATH = _HERE.parents[3] / "infra" / "main.bicepparam"

DEFAULT_MAX_CREDITS = 40


def production_model() -> str | None:
    """The model production runs, so a result is never read as being about it
    when it isn't. Not available outside a checkout of the repo."""
    try:
        params = BICEP_PARAMS_PATH.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"name: 'GEMINI_MODEL', value: '([^']+)'", params)
    return match.group(1) if match else None


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluación de veredictos (gasta cuota gratuita).")
    parser.add_argument("--cases", help="ids separados por comas; por defecto, todos")
    parser.add_argument("--max-credits", type=int, default=DEFAULT_MAX_CREDITS)
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
        for case in cases:
            print(f"- {case.id} ({case.rating}): {case.claim}")
        print(
            f"{len(cases)} casos: {len(cases) * CREDITS_PER_SEARCH} créditos de Tavily"
            f" ({CREDITS_PER_SEARCH} créditos por caso); tope {args.max_credits}"
        )
        return 0

    settings = get_settings()
    if not settings.gemini_api_key or not settings.tavily_api_key:
        # Without them every claim would come back as a failed verification.
        print("Faltan GEMINI_API_KEY y TAVILY_API_KEY en el entorno.", file=sys.stderr)
        return 2

    expected_model = production_model()
    if expected_model and expected_model != settings.gemini_model:
        print(
            f"Aviso: {settings.gemini_model} no es el modelo de producción ({expected_model}).",
            file=sys.stderr,
        )

    run = asyncio.run(
        runner.run_cases(
            cases,
            allowed_domains=runner.load_allowed_domains(TRUSTED_SOURCES_PATH),
            max_credits=args.max_credits,
        )
    )
    RESULTS_DIR.mkdir(exist_ok=True)
    stem = RESULTS_DIR / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    stem.with_suffix(".json").write_text(run.model_dump_json(indent=2), encoding="utf-8")
    report_path = stem.with_suffix(".md")
    report_path.write_text(render_report(run, {c.id: c for c in cases}), encoding="utf-8")
    print(f"Informe: {report_path}")
    print(f"Créditos de Tavily: {run.spent_credits} de {args.max_credits}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
