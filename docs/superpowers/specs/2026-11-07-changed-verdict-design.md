# Veredicto «Cambió con el tiempo»: diseño

**Fecha:** 2026-11-07. **Estado:** pendiente de aprobación del dueño. Sin código todavía.

## Problema

La app solo tiene tres veredictos. Cuando una afirmación no es del todo cierta ni del todo falsa, tiene que elegir uno que no encaja. `co-mixto-1` («la inflación cayó del 13 % a cerca del 5 %», «Cuestionable» en Colombiacheck) volvió a salir `SUPPORTED` en la evaluación del 2026-11-07 (`apps/api/evals/verdicts/results/2026-11-07_115534.md`), y es el único error grave de los 8 casos.

## Decisiones del dueño

1. El usuario debe entender que hubo una actualización, y poder ver lo anterior o ir a la noticia donde aparecía ese dato.
2. **`co-mixto-2`, con una parte cierta y otra falsa, se muestra igual que «cambió con el tiempo».** Hay un solo veredicto nuevo, no dos.

## Diseño

### Veredicto `CHANGED`

- **Etiqueta:** «Cambió con el tiempo». Plural del resumen: «con cambios en el tiempo».
- **Cuándo:** las fuentes confirman una parte de la afirmación o un dato que fue cierto, pero otras fuentes lo matizan, lo actualizan o lo contradicen en parte.
- **Prompt de `verify.py`:** la regla «si es cierta solo en parte, no respondas SUPPORTED» pasa a pedir `CHANGED`. `SUPPORTED` y `CONTRADICTED` siguen reservados para cuando las fuentes apuntan en una sola dirección.
- **Respaldo mínimo:** `_conclude` exige al menos 2 evidencias válidas. Con menos, el resultado es `INSUFFICIENT`, igual que un veredicto direccional sin cita que lo sostenga.
- **Comprobar con la evaluación si hace falta una regla más:** exigir que las citas no sean todas de la misma postura. `co-mixto-1` citó solo `supports`, así que esa regla podría ser demasiado estricta, y se decide con datos.

### Línea de tiempo en el reporte

Una afirmación `CHANGED` muestra sus evidencias como línea de tiempo, de la más antigua a la más reciente. Cada punto lleva fecha, medio, postura y enlace a la noticia. Las evidencias sin fecha van al final, bajo «Sin fecha». No hay datos nuevos que guardar: `Evidence` ya tiene `published_at`, `url` y `stance`.

La ordenación vive en una función pura de `apps/web/lib` con pruebas, porque `published_at` es texto libre que llega en varios formatos.

### Reputación

`update_reputation_for_claim` trata `CHANGED` como `INSUFFICIENT`: no puntúa a nadie. Una fuente de 2022 con el dato de entonces no se equivocó, y penalizarla sería injusto.

### Evaluación

- `scoring.py`: los casos `mixed` esperan `CHANGED`. `SUPPORTED` sigue siendo error grave, y `CONTRADICTED` e `INSUFFICIENT` pasan a ser fallo leve.
- **Nuevo error a vigilar:** un caso `true` o `false` que salga `CHANGED` cuenta como fallo. Si el modelo abusa del veredicto nuevo, se verá ahí.

### Web y API

- `Verdict` en `lib/cases.ts`, `VERDICTS` y `VERDICT_ORDER` en `components/verdict.tsx`, un color propio y `changed` en el resumen del reporte (`reports/schemas.py`, `reports/service.py`).
- La columna `claims.verdict` es texto, así que no hace falta migración.
- La portada explica el cuarto veredicto en su lista (`app/page.tsx`).

## Orden de despliegue

La web debe saber pintar `CHANGED` antes de que la API lo emita: `VERDICTS[v]` sería `undefined` y el reporte fallaría. Por eso son **dos PR, primero la web y después la API**. El resumen acepta `changed` ausente hasta que la API esté desplegada.

## Criterio de aceptación

Con los mismos 8 casos:

- `co-mixto-1` y `co-mixto-2` salen `CHANGED` en 3 ejecuciones seguidas, para descartar el resultado inestable de hasta ahora;
- 0 errores graves;
- ningún caso `true` o `false` cae en `CHANGED`.

Cada ejecución gasta 16 créditos de Tavily, 48 en total.

## Riesgo conocido

`co-mixto-2` no cambió con el tiempo: nunca fue cierto en la parte del porcentaje. Con esta decisión, el usuario leerá «Cambió con el tiempo» sobre un dato que no cambió. La explicación y las evidencias lo aclaran, pero la etiqueta no. Si esto molesta al probarlo, basta con cambiar la etiqueta por una más amplia, sin tocar el resto del diseño.

## Fuera de alcance

- Separar «cambió» de «cierta en parte» en dos veredictos.
- Sacar de la búsqueda los artículos del propio fact-checker. 6 de los 8 casos siguen contaminados, y eso se trata en otro cambio.
