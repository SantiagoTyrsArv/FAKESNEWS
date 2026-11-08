# Ampliar la evaluación de veredictos: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** que la evaluación de veredictos tenga un modo ciego sin verificadores, 20 casos y un informe por modo y por tipo de caso.

**Arquitectura:** la exclusión de dominios vive en un módulo nuevo de la evaluación (`evals/verdicts/blind.py`) y el runner la aplica caso a caso. `run.py` añade la opción `--blind`. Los casos nuevos se buscan con la búsqueda web del asistente y se añaden a `cases.json`. Producción no cambia.

**Tecnologías:** Python 3.12, pydantic, pytest (con `asyncio_mode` automático, como las pruebas actuales).

**Especificación:** [`docs/superpowers/specs/2026-11-08-verdict-eval-expansion-design.md`](../specs/2026-11-08-verdict-eval-expansion-design.md)

## Restricciones globales

- No se toca nada fuera de `apps/api/evals/verdicts/`, `apps/api/tests/evals/` y la documentación.
- Verificadores que se excluyen en modo ciego: `colombiacheck.com`, `lasillavacia.com`, `chequeado.com`, `maldita.es`, `politifact.com` y `factcheck.org`.
- `DEFAULT_MAX_CREDITS` pasa a `60`.
- Reparto final de casos: 6 `false`, 6 `true`, 5 `mixed` y 3 `invented` (20 en total). Los 8 casos actuales no se modifican.
- Buscar casos no gasta Tavily: se usa la búsqueda web del asistente.
- **Ninguna ejecución real** (sin `--dry-run`) sin la aprobación explícita del dueño en ese momento.
- Comprobaciones, desde `apps/api`: `python -m pytest -q`, `uv run ruff check .` y `uv run ruff format --check .`. En Windows, `uv run pytest` falla con «trampoline».

## Puntos que revisar

1. **Caso inventado con `factchecker` vacío en modo ciego:** solo se quitan los verificadores, y la lista no queda vacía ni falla. Prueba en la tarea 1.
2. **Verificador con subdominio** (`factual.afp.com`): en modo ciego se quita también `afp.com`, porque las evidencias se guardan con el dominio de confianza. Prueba en la tarea 1.
3. **Mayúsculas o `www.` en `factchecker`:** se comparan normalizados. Prueba en la tarea 1.
4. **Modo ciego no altera `allowed_domains` del caso siguiente:** la exclusión se calcula por caso sin modificar la lista original. Prueba en la tarea 1.
5. **Ejecución normal sin `--blind`:** se comporta exactamente como antes (mismos dominios, nombre de archivo sin sufijo). Prueba en la tarea 2.

---

### Tarea 1: exclusión de dominios en el runner

**Archivos:**
- Crear: `apps/api/evals/verdicts/blind.py`
- Modificar: `apps/api/evals/verdicts/runner.py` (`RunResult` y `run_cases`)
- Pruebas: `apps/api/tests/evals/test_blind.py` (nueva) y `apps/api/tests/evals/test_runner.py`

**Interfaces:**
- Produce: `FACTCHECKER_DOMAINS: frozenset[str]` y `blind_domains(allowed_domains: list[str], factchecker: str) -> list[str]` en `blind.py`.
- Produce: `run_cases(cases, *, allowed_domains, max_credits, verify=verify_claim, blind: bool = False) -> RunResult`, y `RunResult.blind: bool = False`.
- Consume: `domain_matches(domain, factchecker)` de `scoring.py`.

- [ ] **Paso 1: escribir las pruebas que fallan** en `tests/evals/test_blind.py`

```python
ALLOWED = ["reuters.com", "afp.com", "bbc.com", "colombiacheck.com", "lasillavacia.com",
           "chequeado.com", "maldita.es", "politifact.com", "factcheck.org", "eltiempo.com"]

def test_blind_removes_every_factchecker():
    assert blind_domains(ALLOWED, "newtral.es") == ["reuters.com", "afp.com", "bbc.com", "eltiempo.com"]

def test_blind_removes_the_cases_own_outlet():
    assert "bbc.com" not in blind_domains(ALLOWED, "bbc.com")

def test_blind_removes_parent_of_a_subdomain_factchecker():
    assert "afp.com" not in blind_domains(ALLOWED, "factual.afp.com")

def test_blind_normalizes_the_factchecker():
    assert "bbc.com" not in blind_domains(ALLOWED, "WWW.BBC.com")

def test_blind_with_empty_factchecker_only_drops_factcheckers():
    assert blind_domains(ALLOWED, "") == ["reuters.com", "afp.com", "bbc.com", "eltiempo.com"]

def test_blind_does_not_mutate_its_input():
    before = list(ALLOWED)
    blind_domains(ALLOWED, "bbc.com")
    assert ALLOWED == before
```

Y en `tests/evals/test_runner.py`, con un `verify` falso que guarda los `allowed_domains` que recibe:

```python
async def test_run_cases_blind_passes_reduced_domains_per_case():
    # dos casos: uno de colombiacheck.com y otro con factchecker "bbc.com"
    # allowed_domains=["colombiacheck.com", "bbc.com", "eltiempo.com"], blind=True
    assert seen == [["bbc.com", "eltiempo.com"], ["eltiempo.com"]]
    assert run.blind is True

async def test_run_cases_not_blind_passes_all_domains():
    assert seen == [ALL, ALL] and run.blind is False
```

- [ ] **Paso 2: ejecutarlas y ver que fallan**

Ejecutar: `python -m pytest tests/evals/test_blind.py tests/evals/test_runner.py -q`
Resultado esperado: fallo por `ModuleNotFoundError: evals.verdicts.blind` y por el argumento `blind` desconocido.

- [ ] **Paso 3: implementar `blind_domains` en `blind.py`**

Conserva el orden de `allowed_domains` y quita cada dominio que cumpla `domain_matches(d, f)` con algún `f` de `FACTCHECKER_DOMAINS` o con el `factchecker` del caso, este último solo si no está vacío. Docstring: La Silla Vacía cuenta como verificador por su «Detector de mentiras».

- [ ] **Paso 4: usarlo en `run_cases`**

Con `blind=True`, cada caso llama a `verify` con `blind_domains(allowed_domains, case.factchecker)`; sin la opción, con `allowed_domains` sin cambios. `RunResult` gana `blind: bool = False`.

- [ ] **Paso 5: ejecutar las pruebas y ver que pasan**

Ejecutar: `python -m pytest tests/evals -q`
Resultado esperado: todas pasan.

- [ ] **Paso 6: commit**

```bash
git add apps/api/evals/verdicts/blind.py apps/api/evals/verdicts/runner.py apps/api/tests/evals/test_blind.py apps/api/tests/evals/test_runner.py
git commit -m "feat(evals): modo ciego que excluye a los verificadores de la búsqueda"
```

### Tarea 2: opción `--blind`, tope de créditos e informe

**Archivos:**
- Modificar: `apps/api/evals/verdicts/run.py`, `apps/api/evals/verdicts/report.py` y `apps/api/evals/verdicts/README.md`
- Pruebas: `apps/api/tests/evals/test_cli.py` y `apps/api/tests/evals/test_report.py`

**Interfaces:**
- Consume: `run_cases(..., blind=...)` y `RunResult.blind` de la tarea 1.
- Produce: `--blind` en la línea de comandos; `DEFAULT_MAX_CREDITS = 60`.

- [ ] **Paso 1: escribir las pruebas que fallan**

En `test_cli.py`, con `runner.run_cases` sustituido por uno que guarda sus argumentos y devuelve un `RunResult` vacío:

```python
def test_blind_flag_reaches_runner_and_names_the_report(...):
    assert run_module.main(["--blind"]) == 0
    assert captured["blind"] is True
    assert all(p.stem.endswith("_blind") for p in (tmp_path / "results").iterdir())

def test_without_blind_runner_gets_false_and_no_suffix(...):
    assert run_module.main([]) == 0
    assert captured["blind"] is False
    assert not any(p.stem.endswith("_blind") for p in (tmp_path / "results").iterdir())

def test_default_max_credits_is_60():
    assert run_module.DEFAULT_MAX_CREDITS == 60

def test_dry_run_says_blind_mode(cases_file, capsys):
    assert run_module.main(["--dry-run", "--blind"]) == 0
    assert "Modo: ciego (sin verificadores)" in capsys.readouterr().out
```

En `test_report.py`:

```python
def test_report_states_mode():
    assert "- Modo: ciego (sin verificadores)" in render_report(run_blind, cases)
    assert "- Modo: normal" in render_report(run_normal, cases)

def test_report_scores_by_kind():
    # resultados: false ok, false fail, true ok
    text = render_report(run, cases)
    assert "| `false` | 1 de 2 |" in text
    assert "| `true` | 1 de 1 |" in text
    assert "`mixed`" not in text.split("## Detalle por caso")[0]  # tipos sin casos no salen
```

- [ ] **Paso 2: ejecutarlas y ver que fallan**

Ejecutar: `python -m pytest tests/evals/test_cli.py tests/evals/test_report.py -q`
Resultado esperado: fallan las pruebas nuevas.

- [ ] **Paso 3: implementar**

- `run.py`: `--blind` (`action="store_true"`, ayuda «quita a los verificadores de la búsqueda»). Se pasa a `run_cases`. El nombre del archivo añade `_blind` en modo ciego. `--dry-run` imprime `Modo: ciego (sin verificadores)` o `Modo: normal` antes del recuento.
- `report.py`: una línea `- Modo: …` tras «Búsqueda», y una sección `## Aciertos por tipo` justo después de «Totales», con la tabla `| Tipo | Aciertos |`, una fila por tipo que tenga casos, en el orden `false`, `true`, `mixed` e `invented`.
- `README.md`: una línea de uso con `--blind` y un párrafo corto que explique la contaminación y por qué existe el modo ciego. El tope pasa a 60.

- [ ] **Paso 4: ejecutar las pruebas y ver que pasan**

Ejecutar: `python -m pytest tests/evals -q && uv run ruff check . && uv run ruff format --check .`
Resultado esperado: todo bien.

- [ ] **Paso 5: commit**

```bash
git commit -am "feat(evals): opción --blind, tope de 60 créditos e informe por tipo"
```

### Tarea 3: 12 casos nuevos

**Archivos:**
- Modificar: `apps/api/evals/verdicts/cases.py` (`Case`), `apps/api/evals/verdicts/cases.json` y `apps/api/evals/verdicts/README.md` (sección «Casos»)
- Pruebas: `apps/api/tests/evals/test_cases.py`

**Interfaces:**
- Produce: `Case.coverage_url: str | None = None`.

- [ ] **Paso 1: escribir las pruebas que fallan**

```python
ORIGINAL_IDS = {"co-falso-1", "co-falso-2", "co-verdadero-1", "co-verdadero-2",
                "co-mixto-1", "co-mixto-2", "py-verdadero-1", "co-inventado-1"}

def test_bundled_cases_file_is_valid():
    cases = load_cases(CASES_PATH)
    assert len(cases) == 20
    assert Counter(c.kind for c in cases) == {"false": 6, "true": 6, "mixed": 5, "invented": 3}

def test_original_cases_are_kept():
    assert ORIGINAL_IDS <= {c.id for c in load_cases(CASES_PATH)}

def test_new_verifiable_cases_have_coverage():
    for c in load_cases(CASES_PATH):
        if c.id not in ORIGINAL_IDS and c.kind != "invented":
            assert c.coverage_url and c.coverage_url.startswith("https://"), c.id

def test_coverage_url_is_optional(tmp_path):
    # un caso sin coverage_url se carga con coverage_url None
```

- [ ] **Paso 2: ejecutarlas y ver que fallan**

Ejecutar: `python -m pytest tests/evals/test_cases.py -q`
Resultado esperado: falla por 8 en lugar de 20.

- [ ] **Paso 3: añadir `coverage_url: str | None = None` a `Case`**

- [ ] **Paso 4: buscar los casos con la búsqueda web (sin Tavily)**

Se necesitan 4 `false`, 3 `true`, 3 `mixed` y 2 `invented`. Para cada uno que no sea inventado, comprobar y anotar:

- el enlace, la fecha y la calificación literal del chequeo (o de la noticia, en los verdaderos), preferiblemente de 2026 y de un verificador fuera de la lista de confianza (Newtral, AFP Factual, El Sabueso, EFE Verifica, Ecuador Chequea, Bolivia Verifica…);
- un `coverage_url` de un dominio de `app/data/trusted_sources.json` que **no** esté en `FACTCHECKER_DOMAINS` y que publique los datos que permiten decidir;
- al menos un mixto debe ser un dato que cambió con el tiempo.

En conjunto: como mucho 6 casos nuevos sobre Colombia, al menos 3 países, temas mezclados. Los inventados, plausibles y del estilo de los reales, con `factchecker` y `factcheck_url` vacíos, como `co-inventado-1`. Los ids siguen el patrón `<país>-<tipo>-<n>` (`es-falso-1`, `mx-mixto-1`…). Los casos se eligen antes de correrlos y no se quitan después por fallar.

- [ ] **Paso 5: añadirlos a `cases.json`** detrás de los actuales, y actualizar en el README el número de casos (20) y su reparto.

- [ ] **Paso 6: ejecutar las pruebas y el dry-run**

Ejecutar: `python -m pytest tests/evals -q && uv run python -m evals.verdicts.run --dry-run`
Resultado esperado: pruebas bien; el dry-run lista 20 casos, «40 créditos de Tavily» y «tope 60».

- [ ] **Paso 7: commit**

```bash
git commit -am "feat(evals): 12 casos nuevos con cobertura fuera de los verificadores"
```

### Tarea 4: PR, ejecuciones reales y registro

- [ ] **Paso 1:** comprobaciones completas de la API (`python -m pytest -q`, `ruff check` y `ruff format --check`), push y PR. Fusionar con merge commit cuando `api-check`, `web-check` y SonarCloud estén en verde.
- [ ] **Paso 2: pedir aprobación al dueño** para dos ejecuciones completas (unos 80 créditos de Tavily, de los 1.000 del mes), con el gasto ya hecho este mes. Exportar solo `TAVILY_API_KEY` y `GEMINI_API_KEY` desde el `.env` de la raíz, sin mostrarlas. Cargar todo el `.env` rompe `CORS_ORIGINS`.
- [ ] **Paso 3:** con la aprobación, `uv run python -m evals.verdicts.run` y `uv run python -m evals.verdicts.run --blind`. Comprobar que en modo ciego ningún caso sale contaminado; si alguno sale, la exclusión falla y se para.
- [ ] **Paso 4:** en `docs/ESTADO.md`, una sección con los dos resultados (por tipo y sin contaminados), los créditos gastados y lo que dicen; se actualizan el punto 1 de los pendientes y el historial de PR. Los informes de `results/` se versionan. PR de documentación, como en sesiones anteriores.
