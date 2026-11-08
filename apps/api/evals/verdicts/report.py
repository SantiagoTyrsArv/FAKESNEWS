from evals.verdicts.cases import Case
from evals.verdicts.runner import CaseResult, RunResult
from evals.verdicts.scoring import EXPECTED

_GRADE_LABEL = {"ok": "✓", "fail": "✗", "severe": "✗ grave", "error": "error"}
MODE_LABEL = {False: "normal", True: "ciego (sin verificadores)"}
_KIND_ORDER = ("false", "true", "mixed", "invented")


def _score(results: list[CaseResult]) -> str:
    ok = sum(1 for r in results if r.grade == "ok")
    return f"{ok} de {len(results)}"


def render_report(run: RunResult, cases: dict[str, Case]) -> str:
    lines = [
        "# Evaluación de veredictos",
        "",
        f"- Fecha: {run.started_at:%Y-%m-%d %H:%M} UTC",
        f"- Modelo: `{run.model}`",
        f"- Búsqueda: Tavily, {run.spent_credits} de {run.max_credits} créditos",
        f"- Modo: {MODE_LABEL[run.blind]}",
        "",
        "| Caso | Calificación | Esperado | Obtenido | Resultado | Contaminado |",
        "|---|---|---|---|---|---|",
    ]
    for r in run.results:
        expected = " o ".join(f"`{v}`" for v in sorted(EXPECTED[r.kind]))
        got = f"`{r.got}`" if r.got else "—"
        lines.append(
            f"| {r.case_id} | {r.rating} | {expected} | {got} | {_GRADE_LABEL[r.grade]} |"
            f" {'sí' if r.contaminated else 'no'} |"
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
        lines.append(f"- Sin correr por el tope de créditos: {', '.join(run.skipped_case_ids)}")

    lines += ["", "## Aciertos por tipo", "", "| Tipo | Aciertos |", "|---|---|"]
    for kind in _KIND_ORDER:
        of_kind = [r for r in run.results if r.kind == kind]
        if of_kind:
            lines.append(f"| `{kind}` | {_score(of_kind)} |")

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
            f"- Explicación del modelo: {r.rationale or '—'}",
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
            f"- Dominios encontrados: {searched} ({r.credits} créditos,"
            f" {r.gemini_calls} llamadas a Gemini)"
        )
    return "\n".join(lines) + "\n"
