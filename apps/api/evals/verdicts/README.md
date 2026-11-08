# Evaluación de veredictos

Pasa 8 afirmaciones, 6 de ellas ya calificadas por un fact-checker, por el `verify_claim` real
y compara el veredicto de la app con la calificación publicada. Diseño:
`docs/superpowers/specs/2026-11-03-verdict-eval-design.md`.

**Usa la cuota gratuita de producción:** unos 2 créditos de Tavily por caso. No corre en el CI.

## Uso

Desde `apps/api`, con `GEMINI_API_KEY` y `TAVILY_API_KEY` en el entorno:

```
uv run python -m evals.verdicts.run --dry-run                              # no gasta
uv run python -m evals.verdicts.run --cases co-falso-1,co-verdadero-1      # primera prueba
uv run python -m evals.verdicts.run                                        # todos los casos
uv run python -m evals.verdicts.run --blind                                # sin verificadores
```

- `--max-credits` fija el tope de créditos de Tavily por ejecución (60 por defecto).
- `--blind` quita de la búsqueda a los verificadores de la lista de confianza y el dominio
  del propio caso (ver más abajo). Su informe lleva el sufijo `_blind`.
- La evaluación avisa si `GEMINI_MODEL` no es el modelo de `infra/main.bicepparam`: sus resultados solo hablan del modelo con el que corrió.
- Una afirmación cuya verificación falló cuenta como error de ejecución, no como veredicto.
- Cada ejecución deja en `results/` un JSON con todas las respuestas y un informe en Markdown.
  Se versionan, para releerlos sin volver a gastar cuota.

## Contaminación y modo ciego

Un caso está **contaminado** cuando el veredicto se apoyó en el propio chequeo que sirve de
respuesta: el modelo lo copió en lugar de verificar. En modo normal pasa a menudo, porque
Colombiacheck, La Silla Vacía y otros verificadores están entre las fuentes de confianza; es lo
que ven los usuarios. El modo ciego (`--blind`) los excluye de la búsqueda (`blind.py`), así que
mide si el modelo verifica con medios y organismos. Ningún caso debería salir contaminado en él.

## Casos

`cases.json`. Los casos enlazan a su verificación o noticia publicada, salvo `co-inventado-1`,
que es una afirmación inventada a propósito y debe dar `INSUFFICIENT`. `kind` es `false`, `true`, `mixed` (engañoso, cuestionable…: debe dar `CHANGED`) o `invented`; las equivalencias
con los veredictos de la app están en `scoring.py`.
