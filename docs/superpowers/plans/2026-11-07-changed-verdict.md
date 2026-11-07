# Veredicto «Cambió con el tiempo»: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Estado:** pendiente de aprobación del dueño.

**Goal:** añadir el veredicto `CHANGED` y mostrar sus evidencias como línea de tiempo, para que `co-mixto-1` y `co-mixto-2` dejen de forzarse a un veredicto que no encaja.

**Architecture:** dos PR en orden: primero la web aprende a pintar `CHANGED`, y después la API lo emite. La ordenación de la línea de tiempo es una función pura en `apps/web/lib`. La regla de respaldo mínimo vive en `_conclude`.

**Tech Stack:** FastAPI, Pydantic, Gemini (salida estructurada), Next 16, React 19, Tailwind 4, `node --test`, Playwright.

**Spec:** [2026-11-07-changed-verdict-design.md](../specs/2026-11-07-changed-verdict-design.md)

## Global Constraints

- Valor del veredicto: `CHANGED`. Etiqueta: «Cambió con el tiempo». Plural: «con cambios en el tiempo».
- La web se fusiona y se despliega en Vercel **antes** de fusionar el PR de la API.
- Sin migración: `claims.verdict` es `String(20)`.
- `CHANGED` exige al menos 2 evidencias válidas; con menos, `INSUFFICIENT`.
- `CHANGED` no puntúa reputación.
- `summary.changed` es opcional en la web hasta que la API esté desplegada.
- La evaluación usa `GEMINI_MODEL=gemini-3.5-flash-lite` y exporta solo `TAVILY_API_KEY` y `GEMINI_API_KEY`: cargar todo el `.env` rompe `CORS_ORIGINS`.
- Toda la copia va en español con acentos. El texto de `published_at` no se modifica al guardarlo.

## Review Focus

1. **Evidencias sin fecha, o con texto como «hace 2 días»:** van bajo «Sin fecha» y nunca rompen la página. Prueba en la tarea 1.
2. **Dos evidencias con la misma URL o fecha:** ninguna se pierde y el orden es estable. Prueba en la tarea 1.
3. **Reporte de la API actual, sin `summary.changed`:** se muestra con 0 y sin `NaN`. Prueba e2e en la tarea 3.
4. **Afirmación `CHANGED` con `verification_failed`:** no es un caso real, pero si llega se muestra como fallo, sin línea de tiempo. Prueba en la tarea 2.
5. **`CHANGED` con 2 citas de las que solo 1 es válida:** cuenta solo las válidas y termina en `INSUFFICIENT`. Prueba en la tarea 4.

---

## PR 1: web (`feat/changed-verdict-web`)

### Task 1: Ordenar evidencias por fecha

**Files:**
- Create: `apps/web/lib/evidence-timeline.mjs`
- Test: `apps/web/lib/evidence-timeline.test.mjs`

**Interfaces:**
- Produces: `orderEvidence(evidence) -> { dated: Evidence[], undated: Evidence[] }`. `dated` va de la más antigua a la más reciente.

- [ ] **Step 1: Escribir las pruebas que fallan**

```js
const item = (url, published_at) => ({ url, published_at });

test("orderEvidence: oldest first across date formats", () => {
  const { dated } = orderEvidence([
    item("b", "Wed, 04 Nov 2026 14:33:05 GMT"),
    item("a", "2022-07-01"),
  ]);
  assert.deepEqual(dated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: null and non-dates go to undated, in their order", () => {
  const { dated, undated } = orderEvidence([item("a", null), item("b", "hace 2 días")]);
  assert.deepEqual(dated, []);
  assert.deepEqual(undated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: the same date keeps every item, in the order received", () => {
  const { dated } = orderEvidence([item("a", "2026-01-01"), item("b", "2026-01-01")]);
  assert.deepEqual(dated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: the input is not changed", () => {
  const input = [item("b", "2026-01-01"), item("a", "2020-01-01")];
  orderEvidence(input);
  assert.deepEqual(input.map((e) => e.url), ["b", "a"]);
});
```

- [ ] **Step 2: Comprobar que fallan.** Run: `pnpm test:lib`. Expected: FAIL, el módulo no existe.
- [ ] **Step 3: Implementar `orderEvidence`.** Una fecha vale si `new Date(value)` es válida, el mismo criterio de `format-date.mjs`.
- [ ] **Step 4: Comprobar que pasan.** Run: `pnpm test:lib`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(web): order evidence by date`.

### Task 2: Veredicto y línea de tiempo en la web

**Files:**
- Modify: `apps/web/lib/cases.ts` (`Verdict`; `summary.changed?: number`)
- Modify: `apps/web/app/globals.css` (`--changed`, `--changed-tint`, `--color-changed`, `--color-changed-tint`, `.mark-changed`)
- Modify: `apps/web/components/verdict.tsx` (`VERDICTS.CHANGED`, `VERDICT_ORDER`)
- Modify: `apps/web/components/report/report-view.tsx` (`CHANGED: summary.changed ?? 0`)
- Modify: `apps/web/components/report/claim-card.tsx`
- Create: `apps/web/components/report/evidence-timeline.tsx`
- Modify: `apps/web/app/page.tsx` («Cuatro resultados posibles» y su descripción)

**Interfaces:**
- Consumes: `orderEvidence` de la tarea 1, `EvidenceItem`.
- Produces: `EvidenceTimeline({ evidence }: { evidence: ReportEvidence[] })`.

- [ ] **Step 1: Añadir tipos y estilos.** `VERDICT_ORDER = ["SUPPORTED", "CHANGED", "CONTRADICTED", "INSUFFICIENT"]`. Icono `History` de `lucide-react`. Color propio de tono violeta, con el mismo requisito que `--insufficient`: al menos 4,5:1 sobre tarjeta, fondo y su tinte. Medir el contraste y dejarlo en el comentario del token.
- [ ] **Step 2: Crear `EvidenceTimeline`.** Una lista vertical con línea y punto por evidencia, que reutiliza `EvidenceItem`. Título «Línea de tiempo». Si `undated` no está vacío, un subtítulo «Sin fecha» y sus evidencias al final.
- [ ] **Step 3: Usarla en `ClaimCard`.** Solo con `claim.verdict === "CHANGED" && !claim.verification_failed`. Cualquier otro caso sigue con la lista actual, incluido un `CHANGED` con `verification_failed`.
- [ ] **Step 4: Actualizar la portada.** Título «Cuatro resultados posibles» y descripción exacta: «Las fuentes confirman una parte o un dato que fue cierto, pero otras lo matizan o lo actualizan.»
- [ ] **Step 5: Comprobar.** Run: `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`. Expected: sin errores.
- [ ] **Step 6: Commit** `feat(web): show the CHANGED verdict with a timeline`.

### Task 3: E2E del veredicto

**Files:**
- Modify: `apps/web/e2e/mock-api.ts`
- Modify: `apps/web/e2e/main-flow.spec.ts`

**Interfaces:**
- Consumes: `EvidenceTimeline` de la tarea 2.

- [ ] **Step 1: Añadir la prueba.** En `mock-api.ts`, un caso con una afirmación `CHANGED`, 3 evidencias desordenadas (2 con fecha y 1 sin ella), un `SUPPORTED` y un resumen **sin** `changed`, como el de la API actual.

```ts
test("a CHANGED claim shows its sources oldest first", async ({ page, context }) => {
  await mockApi(page, context);
  // ...entrar y abrir el reporte del caso...
  await expect(page.getByText("Cambió con el tiempo").first()).toBeVisible();
  const items = page.getByTestId("timeline-item");
  await expect(items.first()).toContainText("2022");
  await expect(items.nth(1)).toContainText("2026");
  await expect(page.getByText("Sin fecha")).toBeVisible();
  await expect(page.getByText("NaN")).toHaveCount(0);
});
```

- [ ] **Step 2: Añadir `data-testid="timeline-item"`** en `EvidenceTimeline`.
- [ ] **Step 3: Comprobar.** Run: `pnpm build`, `pnpm test:e2e`. Expected: PASS.
- [ ] **Step 4: Revisar en el navegador** a 375 px y en escritorio, con captura de pantalla.
- [ ] **Step 5: Commit** `test(web): cover the CHANGED report`.
- [ ] **Step 6: Abrir el PR, fusionar con CI y Sonar en verde** y confirmar que Vercel desplegó antes de seguir con el PR 2.

## PR 2: API (`feat/changed-verdict-api`)

### Task 4: Emitir `CHANGED`

**Files:**
- Modify: `apps/api/app/modules/pipeline/verify.py`
- Test: `apps/api/tests/pipeline/test_verify.py`

**Interfaces:**
- Produces: `VerifyResult.verdict` admite `"CHANGED"`. Constante `MIN_CHANGED_EVIDENCE = 2`.

- [ ] **Step 1: Escribir las pruebas que fallan,** con el ayudante que ya usa `test_verify.py` para simular al modelo.

```python
async def test_changed_verdict_keeps_its_evidence() -> None:
    # El modelo responde CHANGED citando los resultados 1 (supports) y 2 (contradicts).
    assert result.verdict == "CHANGED"
    assert len(result.evidence) == 2

async def test_changed_needs_two_valid_citations() -> None:
    # Responde CHANGED citando el 1 y un número inexistente: solo queda 1 válida.
    assert result.verdict == "INSUFFICIENT"
    assert result.rationale.startswith(UNBACKED_VERDICT_NOTE)
```

- [ ] **Step 2: Comprobar que fallan.** Run: `uv run python -m pytest tests/pipeline/test_verify.py -q`. Expected: FAIL por el `Literal`.
- [ ] **Step 3: Implementar.** Añadir `CHANGED` a los dos `Literal`. En `_conclude`, `CHANGED` con menos de `MIN_CHANGED_EVIDENCE` evidencias devuelve el mismo resultado que un veredicto sin respaldo.
- [ ] **Step 4: Cambiar el prompt.** Texto exacto, sustituyendo la regla «Si la afirmación es cierta solo en parte…»:

```
- CHANGED: los resultados confirman una parte de la afirmación o un dato que fue cierto, \
pero otros resultados, o datos más recientes, lo matizan, lo actualizan o lo contradicen en parte.
- Si la afirmación es cierta solo en parte, exagera, mezcla datos ciertos y falsos o su dato \
ya no es el más reciente según las fechas de los resultados, responde CHANGED, nunca \
SUPPORTED ni CONTRADICTED.
```

- [ ] **Step 5: Comprobar que pasan.** Run: `uv run python -m pytest tests/pipeline -q`. Expected: PASS.
- [ ] **Step 6: Commit** `feat(pipeline): add the CHANGED verdict`.

### Task 5: Reputación, reporte y puntuación de la evaluación

**Files:**
- Modify: `apps/api/app/modules/sources/reputation.py`, `apps/api/app/modules/reports/schemas.py`, `apps/api/app/modules/reports/service.py`
- Modify: `apps/api/evals/verdicts/cases.py`, `apps/api/evals/verdicts/scoring.py`, `apps/api/evals/verdicts/README.md`, `docs/reputation.md`
- Test: `apps/api/tests/sources/test_reputation.py`, `apps/api/tests/reports/`, `apps/api/tests/evals/test_scoring.py`

**Interfaces:**
- Produces: `ReportSummary.changed: int`.

- [ ] **Step 1: Escribir las pruebas que fallan.**

```python
async def test_changed_verdict_scores_nobody(db_session) -> None:
    # Dos fuentes independientes en desacuerdo, verdict="CHANGED".
    assert source_a.cases_count == 0 and source_b.cases_count == 0

# test_grade, sustituyendo las filas de "mixed":
("mixed", "CHANGED", "ok"),
("mixed", "CONTRADICTED", "fail"),
("mixed", "INSUFFICIENT", "fail"),
("mixed", "SUPPORTED", "severe"),
("true", "CHANGED", "fail"),
("false", "CHANGED", "fail"),
("invented", "CHANGED", "fail"),

# Prueba del reporte con una afirmación CHANGED:
assert body["summary"]["changed"] == 1
```

- [ ] **Step 2: Comprobar que fallan.** Run: `uv run python -m pytest tests/sources tests/reports tests/evals -q`. Expected: FAIL.
- [ ] **Step 3: Implementar.** `update_reputation_for_claim` sale sin puntuar con `INSUFFICIENT` o `CHANGED`. `changed=verdicts["CHANGED"]`. `Verdict` gana `CHANGED` y `EXPECTED["mixed"]` pasa a `frozenset({"CHANGED"})`. Explicar el caso en `docs/reputation.md` y en el README de la evaluación.
- [ ] **Step 4: Comprobar la suite.** Run: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`. Expected: todo en verde.
- [ ] **Step 5: Commit** `feat: score and report the CHANGED verdict`.

### Task 6: Criterio de aceptación

**Files:**
- Create: 3 informes en `apps/api/evals/verdicts/results/`
- Modify: `docs/ESTADO.md`

- [ ] **Step 1: Correr la evaluación 3 veces.** Run, desde `apps/api`: `uv run python -m evals.verdicts.run`. Gasta 48 créditos de Tavily.
- [ ] **Step 2: Comprobar el criterio de la especificación:** `co-mixto-1` y `co-mixto-2` en `CHANGED` las 3 veces, 0 errores graves y ningún caso `true` o `false` en `CHANGED`.
- [ ] **Step 3: Si no se cumple,** ajustar solo el prompt de la tarea 4 y repetir, como máximo 2 rondas más (96 créditos). Si sigue sin cumplirse, parar y llevar los informes al dueño. No se relaja el criterio ni se añade la regla de posturas sin datos que la justifiquen.
- [ ] **Step 4: Registrar el resultado** en `docs/ESTADO.md`, incluida la decisión sobre la regla de posturas de la especificación.
- [ ] **Step 5: Commit** `docs: record the CHANGED verdict evaluation`.
- [ ] **Step 6: Abrir el PR, confirmar que Vercel ya sirve el PR 1 y fusionar** con CI y Sonar en verde.
- [ ] **Step 7: Comprobar producción tras `api-deploy`:** `/api/health` responde `ok`. No se crean casos de prueba en producción.
