from evals.verdicts.cases import Case
from evals.verdicts.cost import INPUT_USD_PER_MTOK, OUTPUT_USD_PER_MTOK, WEB_SEARCH_USD
from evals.verdicts.runner import CaseResult, RunResult
from evals.verdicts.scoring import EXPECTED

_GRADE_LABEL = {"ok": "✓", "fail": "✗", "severe": "✗ grave", "error": "error"}


def _num(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def usd(value: float) -> str:
    return f"{value:.2f}".replace(".", ",") + " USD"


def _score(results: list[CaseResult]) -> str:
    ok = sum(1 for r in results if r.grade == "ok")
    return f"{ok} de {len(results)}"


def render_report(run: RunResult, cases: dict[str, Case]) -> str:
    lines = [
        "# Evaluación de veredictos",
        "",
        f"- Fecha: {run.started_at:%Y-%m-%d %H:%M} UTC",
        f"- Modelo: `{run.model}`",
        f"- Precios del {run.prices_as_of}: {_num(INPUT_USD_PER_MTOK)} USD por millón de tokens"
        f" de entrada, {_num(OUTPUT_USD_PER_MTOK)} USD por millón de tokens de salida,"
        f" {_num(WEB_SEARCH_USD)} USD por búsqueda web",
        f"- Gasto estimado: {usd(run.spent_usd)} de un tope de {usd(run.max_usd)}",
        "",
        "| Caso | Calificación | Esperado | Obtenido | Resultado | Contaminado | Costo |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in run.results:
        expected = " o ".join(f"`{v}`" for v in sorted(EXPECTED[r.kind]))
        got = f"`{r.got}`" if r.got else "—"
        lines.append(
            f"| {r.case_id} | {r.rating} | {expected} | {got} | {_GRADE_LABEL[r.grade]} |"
            f" {'sí' if r.contaminated else 'no'} | {usd(r.cost_usd)} |"
        )

    clean = [r for r in run.results if not r.contaminated]
    lines += [
        "",
        "## Totales",
        "",
        f"- Aciertos: {_score(run.results)}",
        f"- Aciertos sin los casos contaminados: {_score(clean)}",
        f"- Fallos: {sum(1 for r in run.results if r.grade == 'fail')}",
        f"- Errores graves: {sum(1 for r in run.results if r.grade == 'severe')}",
        f"- Errores de ejecución: {sum(1 for r in run.results if r.grade == 'error')}",
    ]
    if run.skipped_case_ids:
        lines.append(f"- Sin correr por el tope de gasto: {', '.join(run.skipped_case_ids)}")

    lines += ["", "## Detalle por caso"]
    for r in run.results:
        case = cases[r.case_id]
        lines += [
            "",
            f"### {r.case_id}",
            "",
            f"- Afirmación: {case.claim}",
            f"- Verificación: [{case.factchecker}, {case.factcheck_date}]({case.factcheck_url})"
            f" — «{case.rating}»",
            f"- Explicación de Claude: {r.rationale or '—'}",
        ]
        if r.error:
            lines.append(f"- Error: {r.error}")
        if r.evidence:
            lines.append("- Evidencias válidas:")
            lines += [f"  - {e['domain']} ({e['stance']}): {e['url']}" for e in r.evidence]
        else:
            lines.append("- Evidencias válidas: sin evidencias válidas")
        searched = ", ".join(r.search_domains) or "ninguno"
        lines.append(
            f"- Dominios donde buscó: {searched} ({r.web_searches} búsquedas,"
            f" {r.input_tokens} tokens de entrada, {r.output_tokens} de salida)"
        )
    return "\n".join(lines) + "\n"
