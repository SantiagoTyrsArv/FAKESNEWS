# Evaluación de veredictos: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> En este repositorio se ejecuta **en línea, sin subagentes** (preferencia del dueño): superpowers:executing-plans.

**Goal:** Un script manual que pasa 6 afirmaciones colombianas ya calificadas por fact-checkers por el `verify_claim` real, con un freno de gasto, y escribe un informe de aciertos.

**Architecture:** Paquete `apps/api/evals/verdicts/`, fuera de `app/`. Módulos pequeños y puros (casos, calificación, costo, informe) y un `run.py` que los une y llama a las funciones reales del pipeline. El consumo se lee envolviendo `log_usage`, que el pipeline ya llama con cada respuesta, sin cambiar su comportamiento.

**Tech Stack:** Python 3.12, pydantic 2, pytest (`asyncio_mode = "auto"`), SDK `anthropic` 2.x (vía el pipeline existente), `uv`.

**Spec:** `docs/superpowers/specs/2026-11-03-verdict-eval-design.md`

## Global Constraints

- No se llama a la API de Anthropic en ninguna prueba ni en el CI. Solo `run.py` sin `--dry-run` gasta.
- Tope por defecto: **0,75 USD** por ejecución (`--max-usd`).
- Precios (oficiales al 2026-11-03, `claude-sonnet-5`): entrada **2 USD/MTok**, salida **10 USD/MTok**, búsqueda web **0,01 USD** por búsqueda. Constantes con nombre, citadas en el informe.
- Modelo: el configurado (`settings.anthropic_model`), sin cambiarlo.
- Dominios permitidos: los de `app/data/trusted_sources.json`. No se toca ninguna base de datos.
- No se modifica nada de `app/` (ni prompt, ni modelo, ni lógica).
- Equivalencias: falso → `CONTRADICTED`; verdadero → `SUPPORTED`; intermedio → `CONTRADICTED` o `INSUFFICIENT`. Error grave: `SUPPORTED` en falso o intermedio, `CONTRADICTED` en verdadero.
- Todo el texto para el dueño (informe, mensajes de la CLI) va en español. Los comentarios de código, en inglés, como el resto de `apps/api`.
- Comprobaciones: `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .` (desde `apps/api`; en Windows `python -m pytest`, no `uv run pytest`).

## Review Focus

1. **Evidencia de un subdominio** (`factual.afp.com`): desde el PR #51 el pipeline la acepta y la guarda como `afp.com`. La marca de contaminación de un caso de AFP Factual (`factchecker: "factual.afp.com"`) debe reconocerla: `domain_matches` compara en ambos sentidos de subdominio. Prueba en la tarea 1.
2. **El tope se alcanza a mitad de la ejecución:** debe parar *antes* de empezar el caso que lo pasaría, guardar lo hecho y decir cuántos casos quedaron sin correr. Prueba en la tarea 4.
3. **Un caso cuya verificación revienta** (excepción de red no capturada): no debe perder los resultados anteriores. Se registra como `error` y se sigue. Prueba en la tarea 4.
4. **`--cases` con un id que no existe:** debe fallar antes de gastar nada, con un mensaje claro. Prueba en la tarea 4.
5. **Falta `ANTHROPIC_API_KEY`:** sin `--dry-run`, debe abortar antes de llamar a la API, en lugar de convertir cada caso en `INSUFFICIENT` (lo que el pipeline hace con un error de autenticación). Prueba en la tarea 4.

---

### Task 1: Casos y calificación

**Files:**
- Create: `apps/api/evals/__init__.py`, `apps/api/evals/verdicts/__init__.py` (vacíos)
- Create: `apps/api/evals/verdicts/cases.py`
- Create: `apps/api/evals/verdicts/scoring.py`
- Test: `apps/api/tests/evals/__init__.py`, `apps/api/tests/evals/test_cases.py`, `apps/api/tests/evals/test_scoring.py`

**Interfaces:**
- Produces:
  - `Kind = Literal["false", "true", "mixed"]`
  - `Verdict = Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT"]`
  - `class Case(BaseModel)`: `id: str`, `factchecker: str` (dominio), `factcheck_url: str`, `factcheck_date: date`, `rating: str` (texto original), `kind: Kind`, `claim: str`.
  - `load_cases(path: Path) -> list[Case]`: rechaza ids repetidos con `ValueError`.
  - `EXPECTED: dict[Kind, frozenset[Verdict]]` con las equivalencias de las Global Constraints.
  - `Grade = Literal["ok", "fail", "severe", "error"]`
  - `grade(kind: Kind, got: Verdict) -> Grade` (nunca devuelve `"error"`; ese valor lo pone `run.py`).
  - `domain_matches(domain: str, factchecker: str) -> bool`: iguales, o uno subdominio del otro (`factual.afp.com` y `afp.com` coinciden en ambos sentidos; `notafp.com` no).
  - `is_contaminated(evidence_domains: list[str], factchecker: str) -> bool`

Nota de diseño: el documento pedía un campo `expected` por caso; aquí se deriva de `kind` con `EXPECTED`, para no duplicar la tabla en cada caso.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# test_scoring.py
@pytest.mark.parametrize(("kind", "got", "expected"), [
    ("false", "CONTRADICTED", "ok"), ("false", "INSUFFICIENT", "fail"), ("false", "SUPPORTED", "severe"),
    ("true", "SUPPORTED", "ok"), ("true", "INSUFFICIENT", "fail"), ("true", "CONTRADICTED", "severe"),
    ("mixed", "CONTRADICTED", "ok"), ("mixed", "INSUFFICIENT", "ok"), ("mixed", "SUPPORTED", "severe"),
])
def test_grade(kind, got, expected):
    assert grade(kind, got) == expected

def test_domain_matches_subdomain():
    assert domain_matches("factual.afp.com", "afp.com")
    assert domain_matches("afp.com", "afp.com")
    assert not domain_matches("notafp.com", "afp.com")
    # Evidence is stored under the trusted domain (PR #51); the case names the desk.
    assert domain_matches("afp.com", "factual.afp.com")

def test_is_contaminated():
    assert is_contaminated(["reuters.com", "colombiacheck.com"], "colombiacheck.com")
    assert not is_contaminated(["reuters.com"], "colombiacheck.com")
    assert not is_contaminated([], "colombiacheck.com")

# test_cases.py
def test_load_cases_rejects_duplicate_ids(tmp_path): ...  # pytest.raises(ValueError)
def test_load_cases_rejects_unknown_kind(tmp_path): ...   # pytest.raises(ValidationError)
def test_bundled_cases_file_is_valid():
    cases = load_cases(CASES_PATH)
    assert len(cases) == 6
    assert sorted(c.kind for c in cases) == ["false", "false", "mixed", "mixed", "true", "true"]
```

`CASES_PATH` es `Path(evals.verdicts.__file__).parent / "cases.json"`. `test_bundled_cases_file_is_valid` sigue fallando hasta la tarea 5; márcala `@pytest.mark.skip(reason="cases.json llega en la tarea 5")` y quita la marca en la tarea 5.

- [ ] **Step 2: Correr y ver que fallan** — `uv run python -m pytest tests/evals -q` → `ModuleNotFoundError: evals`.
- [ ] **Step 3: Implementar `cases.py` y `scoring.py`** con las interfaces de arriba. `domain_matches` normaliza ambos lados con `app.modules.sources.service.normalize_domain`.
- [ ] **Step 4: Correr y ver que pasan** — mismo comando, todo verde (1 omitida).
- [ ] **Step 5: Commit** — `feat(evals): add verdict eval cases model and grading`

### Task 2: Medidor de costo y freno

**Files:**
- Create: `apps/api/evals/verdicts/cost.py`
- Test: `apps/api/tests/evals/test_cost.py`

**Interfaces:**
- Produces:
  - `INPUT_USD_PER_MTOK = 2.0`, `OUTPUT_USD_PER_MTOK = 10.0`, `WEB_SEARCH_USD = 0.01`, `PRICES_AS_OF = "2026-11-03"`
  - `call_cost(input_tokens: int, output_tokens: int, web_searches: int) -> float`
  - `class UsageMeter`: `record(response) -> None` (lee `response.usage.input_tokens`, `.output_tokens`, `.server_tool_use.web_search_requests` con `server_tool_use` posiblemente `None`, y guarda la `url` de cada `web_search_result` dentro de los bloques `web_search_tool_result` de `response.content`, saltando los que traen un objeto de error en vez de una lista); propiedades `spent_usd: float`, `input_tokens`, `output_tokens`, `web_searches`, `search_result_urls: list[str]` (el informe los lista por caso, para ver dónde buscó Claude aunque no citara nada).
  - `metering(meter: UsageMeter)`: context manager que reemplaza `app.modules.pipeline.verify.log_usage` y `app.modules.pipeline.claims.log_usage` por una función que llama a la original **y** a `meter.record(response)`; restaura ambas al salir, también si hay excepción.
  - `class BudgetGuard(max_usd: float)`: `can_start(spent_usd: float, largest_case_usd: float) -> bool` → `spent_usd + largest_case_usd <= max_usd`. Para el primer caso (`largest_case_usd == 0`) usa `FIRST_CASE_ESTIMATE_USD = 0.35` (el máximo estimado con reintento en el documento).

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
def test_call_cost():
    assert call_cost(1_000_000, 0, 0) == pytest.approx(2.0)
    assert call_cost(0, 1_000_000, 0) == pytest.approx(10.0)
    assert call_cost(0, 0, 3) == pytest.approx(0.03)

def test_meter_handles_missing_server_tool_use(): ...  # usage.server_tool_use=None → web_searches == 0
def test_meter_collects_search_result_urls(): ...       # list content → urls kept; error-object content → skipped

async def test_metering_records_verify_calls_and_restores(monkeypatch):
    # Fake client as in tests/pipeline/test_verify.py; usage with web_search_requests=2.
    # Inside `with metering(meter)`: await verify_claim(...). Then:
    assert meter.web_searches == 2
    assert verify_module.log_usage is original_log_usage  # restored after the block

def test_metering_restores_on_exception(): ...

def test_budget_guard():
    guard = BudgetGuard(0.75)
    assert guard.can_start(0.0, 0.0)            # 0 + 0.35 <= 0.75
    assert guard.can_start(0.40, 0.30)          # 0.70
    assert not guard.can_start(0.50, 0.30)      # 0.80 > 0.75
```

- [ ] **Step 2: Correr y ver que fallan.**
- [ ] **Step 3: Implementar `cost.py`.**
- [ ] **Step 4: Correr y ver que pasan.**
- [ ] **Step 5: Commit** — `feat(evals): add usage meter and budget guard`

### Task 3: Ejecución de un caso y del conjunto

**Files:**
- Create: `apps/api/evals/verdicts/runner.py`
- Test: `apps/api/tests/evals/test_runner.py`

**Interfaces:**
- Consumes: `Case`, `grade`, `is_contaminated` (tarea 1); `UsageMeter`, `metering`, `BudgetGuard` (tarea 2); `app.modules.pipeline.verify.verify_claim(claim_text, *, allowed_domains) -> VerifyResult`.
- Produces:
  - `load_allowed_domains(path: Path) -> list[str]`: los `domain` de `trusted_sources.json`, en orden.
  - `class CaseResult(BaseModel)`: `case_id`, `kind`, `rating`, `got: Verdict | None`, `grade: Grade`, `rationale: str`, `evidence: list[dict]` (url, domain, stance), `contaminated: bool`, `search_domains: list[str]` (dominios normalizados de los resultados de búsqueda de este caso, sin repetir), `cost_usd: float`, `input_tokens`, `output_tokens`, `web_searches: int`, `error: str | None`.
  - `class RunResult(BaseModel)`: `started_at: datetime`, `model: str`, `max_usd: float`, `prices_as_of: str`, `results: list[CaseResult]`, `skipped_case_ids: list[str]` (los que no corrieron por el tope), `spent_usd: float`.
  - `async def run_cases(cases: list[Case], *, allowed_domains: list[str], max_usd: float, verify=verify_claim) -> RunResult`: uno por uno; antes de cada caso pregunta a `BudgetGuard` con el costo del caso más caro visto; si no puede, el resto va a `skipped_case_ids` y se detiene. El costo de un caso es la diferencia de `meter.spent_usd` antes y después. Una excepción de `verify` da `grade="error"`, `got=None` y `error=str(exc)`, y se sigue con el siguiente caso.

- [ ] **Step 1: Escribir las pruebas que fallan** (con un `verify` falso que llama a `verify_module.log_usage(...)` con una respuesta de uso fijo, para que el medidor cuente, y devuelve un `VerifyResult`):

```python
async def test_run_cases_grades_and_costs(): ...
    # 2 cases, fake verify returns CONTRADICTED with evidence on colombiacheck.com
    assert [r.grade for r in run.results] == ["ok", "severe"]  # case kinds: false, true
    assert run.results[0].contaminated is True
    assert run.spent_usd == pytest.approx(sum(r.cost_usd for r in run.results))

async def test_run_cases_stops_before_exceeding_budget():
    # each fake call costs 0.30; max_usd=0.75 → runs 2, skips the rest
    assert len(run.results) == 2
    assert run.skipped_case_ids == ["c3", "c4"]

async def test_run_cases_records_exception_and_continues():
    # fake verify raises on the first case only
    assert run.results[0].grade == "error" and run.results[0].got is None
    assert run.results[1].grade == "ok"

def test_load_allowed_domains_reads_trusted_sources():
    domains = load_allowed_domains(Path("app/data/trusted_sources.json"))
    assert "colombiacheck.com" in domains and len(domains) == 25
```

- [ ] **Step 2: Correr y ver que fallan.**
- [ ] **Step 3: Implementar `runner.py`.** `verify` es un parámetro para poder inyectar el falso; por defecto, el real.
- [ ] **Step 4: Correr y ver que pasan.**
- [ ] **Step 5: Commit** — `feat(evals): run verdict cases under a spend cap`

### Task 4: Informe y CLI

**Files:**
- Create: `apps/api/evals/verdicts/report.py`
- Create: `apps/api/evals/verdicts/run.py`
- Create: `apps/api/evals/verdicts/results/.gitkeep`
- Test: `apps/api/tests/evals/test_report.py`, `apps/api/tests/evals/test_cli.py`

**Interfaces:**
- Consumes: `RunResult`, `CaseResult`, `run_cases`, `load_allowed_domains` (tarea 3); `load_cases`, `Case` (tarea 1); constantes de precio (tarea 2).
- Produces:
  - `render_report(run: RunResult, cases: dict[str, Case]) -> str`: Markdown en español con:
    1. Encabezado: fecha, modelo, precios usados (`PRICES_AS_OF` y las tres tarifas), tope y gasto.
    2. Tabla: id, calificación original (`rating`), esperado (de `EXPECTED`), obtenido, resultado (`✓`, `✗`, `✗ grave`, `error`), contaminado (`sí`/`no`) y costo.
    3. Totales: aciertos sobre corridos, fallos, errores graves, errores, la nota **sin** los casos contaminados y los casos omitidos por el tope.
    4. Por caso: la afirmación, el enlace a la verificación, el `rationale` y las evidencias (dominio, URL, postura), o «sin evidencias válidas».
  - `main(argv: list[str] | None = None) -> int` en `run.py`, lanzado con `uv run python -m evals.verdicts.run`. Argumentos: `--cases id1,id2` (por defecto, todos), `--max-usd` (0,75), `--dry-run`. Escribe `results/<AAAA-MM-DD_HHMMSS>.json` (`RunResult.model_dump_json(indent=2)`) y `results/<mismo>.md`, e imprime la ruta del informe y el gasto.
  - Exit codes: `0` bien (aunque haya fallos de veredicto), `2` argumentos inválidos (id desconocido, falta la clave).

El nivel 2 del documento no se implementa en este plan: el dueño lo dejó fuera de esta ejecución y necesita una aprobación aparte.

- [ ] **Step 1: Escribir las pruebas que fallan**

```python
# test_report.py
def test_report_marks_severe_and_contaminated(): ...
    md = render_report(run, cases)
    assert "✗ grave" in md and "| sí |" in md
    assert "2 USD" in md and "0,01 USD" in md           # prices shown
def test_report_score_without_contaminated(): ...       # 2 ok (1 contaminated) of 3 → "1 de 2" sin contaminados
def test_report_lists_skipped_cases(): ...

# test_cli.py
def test_unknown_case_id_exits_2_without_calling_api(monkeypatch, capsys):
    # monkeypatch runner.run_cases to fail the test if called
    assert main(["--cases", "nope"]) == 2
    assert "nope" in capsys.readouterr().err
def test_missing_api_key_exits_2(monkeypatch): ...      # settings.anthropic_api_key = "" and no --dry-run
def test_dry_run_prints_cases_and_estimate_without_calling_api(monkeypatch, capsys): ...
    # output lists the case ids and "estimado" with 6 × 0,06–0,18 USD
def test_run_writes_json_and_report(tmp_path, monkeypatch): ...
    # results dir patched to tmp_path; fake run_cases → both files exist
```

- [ ] **Step 2: Correr y ver que fallan.**
- [ ] **Step 3: Implementar `report.py` y `run.py`.** Los montos se formatean con coma decimal (`0,75 USD`), como en el resto de los textos para el dueño. La clave se comprueba con `get_settings().anthropic_api_key`.
- [ ] **Step 4: Correr y ver que pasan.**
- [ ] **Step 5: Commit** — `feat(evals): add verdict eval report and CLI`

### Task 5: Los 6 casos

**Files:**
- Create: `apps/api/evals/verdicts/cases.json`
- Modify: `apps/api/tests/evals/test_cases.py` (quitar el `skip`)
- Create: `apps/api/evals/verdicts/README.md`

- [ ] **Step 1: Buscar las verificaciones.** En colombiacheck.com, lasillavacia.com (Detector de mentiras) y factual.afp.com: 2 «falso», 2 «verdadero» y 2 intermedias, de temas distintos (política, salud, economía, orden público), cuyo veredicto no dependa de una imagen o un video, y al menos una de cada verificador si es posible. Por cada una se anota la fecha, la calificación textual y la afirmación **tal como la formuló el verificador**. Nada se inventa: si no se encuentra una verificación adecuada, se dice en el PR.
- [ ] **Step 2: Escribir `cases.json`** con ids cortos (`co-falso-1`, `co-verdadero-1`, `co-mixto-1`…).
- [ ] **Step 3: Quitar el `skip`** y correr `uv run python -m pytest tests/evals -q` → todo verde.
- [ ] **Step 4: `README.md`** corto: qué es, que gasta créditos reales de la misma clave de producción, cómo lanzarlo (`--dry-run` primero, luego `--cases` con 2 ids), dónde quedan los resultados, y la recomendación de poner un límite de gasto en la consola de Anthropic.
- [ ] **Step 5: `--dry-run`** — `uv run python -m evals.verdicts.run --dry-run` lista los 6 casos y el costo estimado, sin llamar a la API.
- [ ] **Step 6: Comprobaciones completas** — `uv run python -m pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, todo verde.
- [ ] **Step 7: Commit** — `feat(evals): add six Colombian fact-checked cases`

### Task 6: PR y primera ejecución (gasta créditos; requiere aprobación del dueño)

- [ ] **Step 1: PR** con el documento, el plan y el código. Fusionar cuando el CI y Sonar estén en verde.
- [ ] **Step 2: Pedir aprobación explícita del dueño** para gastar, y confirmar que `ANTHROPIC_API_KEY` está en `apps/api/.env`, que está en `.gitignore` y que la consola tiene un límite de gasto.
- [ ] **Step 3: Ejecutar 2 casos** — `uv run python -m evals.verdicts.run --cases co-falso-1,co-verdadero-1`. Reportar al dueño el costo real por caso y los veredictos.
- [ ] **Step 4: Con su decisión,** correr los 4 restantes (o no), versionar `results/` y resumir en `docs/ESTADO.md`: nota, errores graves, costo real por afirmación y la proyección del costo por envío de producción (× 8 afirmaciones).
