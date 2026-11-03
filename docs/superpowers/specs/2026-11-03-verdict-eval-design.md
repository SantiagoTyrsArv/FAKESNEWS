# Evaluación de la calidad de los veredictos

Fecha: 2026-11-03. Estado: aprobado por el dueño (6 casos, solo nivel 1, tope 0,75 USD).

## Intención

Hasta hoy nunca se ha comprobado que la verificación acierte con el Claude real: las pruebas de `claims.py`, `verify.py` y el orquestador usan un cliente falso. El dueño compró créditos de la API **para comprobar que los veredictos son correctos**, no para probar que la aplicación no se rompe (eso queda para el e2e del punto 3 de `docs/ESTADO.md`, que sigue pendiente).

La evaluación pasa un conjunto pequeño de noticias colombianas, cuyo veredicto ya publicó un medio de fact-checking, por el pipeline real, y compara lo que dice la app con lo que dijo el verificador.

## Contexto que condiciona el diseño

- **Lo que la gente manda:** sobre todo enlaces a artículos, sobre todo de Colombia (dicho por el dueño).
- **El veredicto es por afirmación:** `claims.extract_claims` saca hasta 8 afirmaciones de un texto y `verify.verify_claim` califica cada una como `SUPPORTED`, `CONTRADICTED` o `INSUFFICIENT`, con búsqueda web limitada a los dominios de confianza. No hay un veredicto global por caso.
- **Fuentes colombianas:** se agregaron en el PR #50 (Colombiacheck, La Silla Vacía, El Tiempo, El Espectador, El Colombiano, DANE, Registraduría, Banco de la República y Minsalud). Antes no había ninguna.
- **Presupuesto:** el dueño tiene 5 USD en total y no va a gastar más. **Es la misma clave de API que usa producción**: todo lo que gaste la evaluación se le quita a los usuarios reales.

## Objetivos

1. Un conjunto de **6 casos** colombianos: 2 calificados «falso», 2 «verdadero» y 2 con calificación intermedia («engañoso», «cuestionable», «impreciso», etc.). Cada caso sale de una verificación publicada por Colombiacheck, el Detector de mentiras de La Silla Vacía o AFP Factual, con su enlace. Ningún veredicto esperado lo inventa quien construye.
2. **Nivel 1 (prioritario): solo el verificador.** Se llama a `verify_claim` con la afirmación tal como la formuló el fact-checker y se compara con la calificación esperada.
3. **Nivel 2 (fuera de esta ejecución; el script lo soporta pero no se corre sin nueva aprobación del dueño): recorrido completo.** Para 1 caso, con `MAX_CLAIMS_PER_SUBMISSION=3` en local, se pasa el texto guardado del artículo por `extract_claims` y luego por `verify_claim`, y se revisa (a) si alguna afirmación extraída corresponde a la afirmación central calificada y (b) si su veredicto coincide.
4. **Un informe** legible por el dueño: por caso, lo esperado, lo que dijo la app, la explicación de Claude, las fuentes citadas y el costo. Con totales de aciertos y de errores graves.
5. **Freno de gasto** con tope por ejecución; por defecto **0,75 USD**.

## No objetivos

- No corre en el CI ni en cada PR. Se lanza a mano.
- No repite cada caso varias veces para medir variabilidad: duplicaría el gasto.
- No cambia el prompt, el modelo ni la lógica del pipeline. Si la evaluación muestra problemas, se arreglan en otro cambio y se vuelve a medir.
- No es el e2e con Playwright (registro → envío → veredicto); ese sigue pendiente aparte.

## Anti-objetivos (sería un fracaso aunque funcione)

- Gastar más que el tope, o una cantidad que deje a producción sin saldo.
- Veredictos esperados inventados o sin fuente publicada.
- Crear datos en producción (cuentas, casos, puntajes de fuentes). La evaluación no toca ninguna base de datos.
- Un resultado que cambie solo porque un enlace se cayó: el texto de cada artículo se guarda en el repositorio.

## Equivalencias entre calificaciones

| Calificación del fact-checker | Veredictos aceptados | Error grave |
|---|---|---|
| Falso | `CONTRADICTED` | `SUPPORTED` |
| Verdadero | `SUPPORTED` | `CONTRADICTED` |
| Intermedia (engañoso, cuestionable, impreciso, sacado de contexto…) | `CONTRADICTED` o `INSUFFICIENT` | `SUPPORTED` |

`INSUFFICIENT` en un caso falso o verdadero cuenta como fallo, pero **no grave**: el informe los separa.

## Contaminación por el propio fact-checker

Colombiacheck, La Silla Vacía y AFP (vía `afp.com`) están entre los dominios de confianza, así que Claude puede encontrar la propia verificación y «copiar» la respuesta. En producción eso es legítimo: es lo que pasa con un bulo viral ya desmentido. Pero infla la nota. El informe marca cada caso en el que alguna evidencia validada viene del mismo dominio que la verificación del caso, y da la nota con y sin esos casos.

De paso, el informe dice si alguna evidencia vino de `factual.afp.com`. Eso responde si la búsqueda acepta los subdominios de `afp.com`.

## Costo estimado (precios oficiales del 2026-11-03)

`claude-sonnet-5`: 2 USD por millón de tokens de entrada y 10 USD por millón de tokens de salida. Búsqueda web: 10 USD por cada 1.000 búsquedas, y sus resultados cuentan como tokens de entrada. Estimaciones, pendientes de medir:

| Acción | Estimación |
|---|---|
| Verificar 1 afirmación (nivel 1) | 0,06–0,18 USD (hasta ~0,35 con reintento) |
| Primera prueba (2 casos) | ~0,15–0,35 USD |
| Nivel 1 completo (6 casos) | ~0,40–1,10 USD |
| 1 artículo de nivel 2 con 8 afirmaciones (igual que un envío real de producción) | ~0,50–1,50 USD |

Hallazgo para producción: cada envío de un usuario cuesta lo mismo que un artículo de nivel 2. Las palancas de ahorro (esfuerzo `medium` en `verify`, máximo de búsquedas de 5 a 3 y máximo de afirmaciones de 8 a 4) quedan para cambios aparte, que se medirán con esta evaluación.

## Lo que decidió el dueño

- Que lo importante es que los veredictos sean correctos.
- Que el conjunto salga de verificaciones publicadas por Colombiacheck, La Silla Vacía y AFP Factual.
- Agregar primero las fuentes colombianas (hecho, PR #50).
- Presupuesto total de 5 USD, en la misma clave que producción.
- 6 casos, solo nivel 1 y tope de 0,75 USD por ejecución (la recomendación de ahorro).

## Decisiones de quien diseña (corregibles)

- Tope por defecto de 0,75 USD por ejecución; se puede cambiar con un argumento.
- **Primera ejecución con 2 casos** de nivel 1 para medir el costo real por caso antes de lanzar el resto.
- Los dominios permitidos salen de `app/data/trusted_sources.json`, no de una base de datos: así es reproducible y no hace falta levantar Postgres.
- Se usa el modelo configurado (`ANTHROPIC_MODEL`, hoy `claude-sonnet-5`), el mismo de producción. Medir otro modelo no tiene sentido aquí.
- Recomendación al dueño, no requisito: crear una clave aparte en un *workspace* propio de la consola de Anthropic, con su límite de gasto, para que la evaluación no pueda vaciar lo de producción. Y en cualquier caso poner un límite de gasto en la consola: el script solo *estima*, la consola sí corta.

## Forma de la solución

### Dónde vive

`apps/api/evals/verdicts/`, fuera de `app/` porque no es parte del servicio:

- `cases.json`: los casos.
- `articles/<id>.txt`: el texto guardado de cada artículo de nivel 2.
- `run.py`: el script. Se lanza con `uv run python -m evals.verdicts.run` desde `apps/api`.
- `results/`: un JSON por ejecución con todas las respuestas, y el informe en Markdown. Se versionan, para poder releer una ejecución sin volver a pagar.

### Cada caso

- `id`, `factchecker` (dominio), `factcheck_url`, `factcheck_date`.
- `rating`: la calificación original, tal como la publicó el verificador.
- `expected`: lista de veredictos aceptados, según la tabla de equivalencias.
- `claim`: la afirmación tal como la formuló el fact-checker.
- `article_url` y `article_file` (opcionales, solo nivel 2). Si el bulo era un post de redes sin artículo, el texto guardado es el que cita la verificación.

### Ejecución

- Argumentos: `--level 1|2`, `--cases id1,id2` (o todos), `--max-usd 1.50`, `--dry-run` (lista lo que correría y su costo estimado sin llamar a la API).
- Corre los casos **uno por uno**, no en paralelo: así el freno de gasto puede parar entre caso y caso.
- **Freno:** acumula `input_tokens`, `output_tokens` y `server_tool_use.web_search_requests` de cada respuesta de la API. Antes de empezar un caso, si lo gastado más el costo del caso más caro visto hasta ahora pasaría el tope, se detiene y lo dice. Los precios por token y por búsqueda son constantes en el script, tomadas de la documentación oficial vigente al implementar, y el informe dice qué precios usó.
- Llama a las funciones reales `verify_claim` y `extract_claims`, sin copiar su lógica. Para leer el consumo hay que interceptar las respuestas; el mecanismo lo decide quien construye (por ejemplo, envolver el cliente de `get_anthropic_client`). No se cambia el comportamiento del pipeline.

### Informe

- Una tabla por caso: id, calificación original, esperado, obtenido, ✓/✗/✗ grave, marca de contaminación y costo.
- Debajo de cada caso, la explicación (`rationale`) y las evidencias validadas (dominio, URL y postura).
- Totales: aciertos, fallos, errores graves, nota sin los casos contaminados y gasto total frente al tope.
- En nivel 2, además: las afirmaciones extraídas y cuál se emparejó con la central, o «ninguna». El emparejamiento lo marca quien revisa el informe; el script solo muestra las afirmaciones al lado de la central. Automatizarlo costaría otra llamada a Claude.

### Pruebas (sin gastar)

Pruebas unitarias en `apps/api/tests/evals/` con un cliente falso: equivalencias y clasificación de errores, detección de contaminación, freno de gasto (para antes de pasar el tope) y cálculo de costo. Corren en el `pytest` normal y nunca llaman a la API.

## Lo que queda a quien construye

- Buscar y elegir los 6 casos en los sitios de los tres verificadores: preferir verificaciones recientes, de temas variados (política, salud, economía, orden público) y cuyo veredicto no dependa de una imagen o un video.
- La estructura interna de `run.py` y el formato exacto del JSON de resultados.
- Cómo interceptar el consumo sin cambiar el pipeline.

## Orden de trabajo

1. Casos, script y pruebas unitarias, en un PR. Ninguna llamada real todavía.
2. Con la aprobación del dueño: ejecución de 2 casos de nivel 1. Se reporta el costo real por caso.
3. Con ese dato, el dueño decide si se corren los 4 casos restantes del nivel 1. El nivel 2 necesita una aprobación aparte.
4. El informe final se versiona y se resume en `docs/ESTADO.md`.
