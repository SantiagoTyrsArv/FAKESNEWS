# Evaluación de veredictos

Pasa 6 afirmaciones colombianas, ya calificadas por un fact-checker, por el `verify_claim` real
y compara el veredicto de la app con la calificación publicada. Diseño:
`docs/superpowers/specs/2026-11-03-verdict-eval-design.md`.

**Gasta créditos reales de la API, de la misma clave que usa producción.** No corre en el CI.
Antes de usarla, pon un límite de gasto en la consola de Anthropic: el script solo *estima*
lo gastado; la consola sí corta.

## Uso

Desde `apps/api`, con `ANTHROPIC_API_KEY` en `apps/api/.env` o en el entorno:

```
uv run python -m evals.verdicts.run --dry-run                              # no gasta
uv run python -m evals.verdicts.run --cases co-falso-1,co-verdadero-1      # primera prueba
uv run python -m evals.verdicts.run                                        # los 6 casos
```

- `--max-usd` fija el tope por ejecución (por defecto 0,75 USD). El script se detiene antes
  de empezar un caso que pasaría el tope.
- Cada ejecución deja en `results/` un JSON con todas las respuestas y un informe en Markdown.
  Se versionan, para releerlos sin volver a pagar.

## Casos

`cases.json`. Cada caso enlaza a su verificación publicada; ningún veredicto esperado es
inventado. `kind` es `false`, `true` o `mixed` (engañoso, cuestionable…); las equivalencias
con los veredictos de la app están en `scoring.py`.
