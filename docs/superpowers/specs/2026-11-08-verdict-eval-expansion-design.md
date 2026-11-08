# Ampliar la evaluación de veredictos con casos limpios

Fecha: 2026-11-08. Punto 1 de «Pendiente, por prioridad» en [ESTADO.md](../../ESTADO.md).

## Por qué

La evaluación (`apps/api/evals/verdicts/`) da 7 de 8, pero ese número dice poco: 6 de los 8 casos están **contaminados**, es decir, el veredicto se apoyó en el propio artículo del verificador que sirve de respuesta. Los 7 casos con fuente vienen de Colombiacheck, La Silla Vacía o la BBC, y las tres están en `app/data/trusted_sources.json`. La búsqueda encuentra el chequeo publicado y el modelo lo repite. Así se mide si el modelo lee bien un veredicto ajeno, no si sabe verificar.

Antes de tocar otra vez el prompt (por ejemplo, por `co-mixto-1`), hace falta una evaluación cuyo resultado signifique algo: más casos y la mayoría limpios.

## Objetivos

1. **Modo ciego:** una opción de la evaluación que quita de la búsqueda los dominios de los verificadores, para que ningún caso pueda copiar un chequeo publicado.
2. **Más casos:** pasar de 8 a 20, repartidos entre los cuatro tipos y con temas y países variados.
3. **Informe que separe lo que importa:** el resultado por modo, por tipo de caso y sin los contaminados.

## No objetivos

- No se cambia nada de producción: ni el prompt, ni `verify.py`, ni las fuentes de confianza.
- No se intenta arreglar `co-mixto-1`. Esta evaluación es la que dirá después si un cambio lo arregla sin romper otros.
- No corre en el CI, igual que ahora.

## Antiobjetivos

- **Elegir casos porque la app los acierta.** Los casos se escogen antes de correrlos y no se quitan después por haber fallado.
- **Casos imposibles en modo ciego:** una afirmación que solo cubrió un verificador no tiene respuesta sin él, y su `INSUFFICIENT` sería correcto pero contaría como fallo. Cada caso nuevo debe tener cobertura en al menos una fuente de confianza que no sea un verificador.
- **Inventadas absurdas:** una afirmación inventada que nadie creería no prueba nada. Deben sonar plausibles.

## Restricciones

- **Cuota:** cada caso gasta unos 2 créditos de Tavily, de los 1.000 gratuitos al mes, y una llamada a Gemini en el plan gratuito. Con 20 casos, una ejecución completa cuesta unos 40 créditos, y las dos modalidades, unos 80. Nunca se lanza una ejecución real sin la aprobación del dueño.
- **La búsqueda de casos no gasta Tavily:** se hace con la búsqueda web del asistente, no con la clave de producción.
- **Conocimiento previo del modelo:** se prefieren chequeos de 2026, para que el modelo no conozca la respuesta de antemano.

## Diseño

### Modo ciego (`--blind`)

- `run.py` acepta `--blind`. Sin la opción, la evaluación se comporta como ahora, que es lo que ven los usuarios.
- En modo ciego, para cada caso, `allowed_domains` pierde:
  - los verificadores de la lista de confianza: `colombiacheck.com`, `lasillavacia.com`, `chequeado.com`, `maldita.es`, `politifact.com` y `factcheck.org`;
  - el dominio de `factchecker` del propio caso, aunque sea un medio (por ejemplo, `bbc.com` en `py-verdadero-1`).
- La lista de verificadores vive en la evaluación (`evals/verdicts/`), no en producción. *Decisión del autor:* La Silla Vacía cuenta como verificador, aunque también es un medio, porque su «Detector de mentiras» publica calificaciones.
- El informe y el JSON registran el modo. El nombre del archivo lleva `_blind` en modo ciego, para no confundir ejecuciones.
- La columna «Contaminado» se mantiene en los dos modos. En modo ciego debería salir siempre «no»; un «sí» indicaría que la exclusión falla.

### Casos nuevos

Reparto final (20 casos):

| Tipo | Ahora | Nuevos | Total |
|---|---|---|---|
| `false` | 2 | 4 | 6 |
| `true` | 3 | 3 | 6 |
| `mixed` | 2 | 3 | 5 |
| `invented` | 1 | 2 | 3 |

Criterios para cada caso nuevo:

- **Fuente de la respuesta:** un chequeo publicado, o una noticia en el caso de los verdaderos, con enlace, fecha y calificación literal, como los actuales. Se prefieren verificadores **fuera** de la lista de confianza, como Newtral, AFP Factual, El Sabueso (Animal Político), EFE Verifica, Ecuador Chequea o Bolivia Verifica: así el caso es limpio también en modo normal.
- **Cobertura:** antes de añadirlo, se comprueba con la búsqueda web que al menos un medio u organismo de confianza que no sea un verificador (El Tiempo, El País, Reuters, la BBC, el DANE…) publicó los datos que permiten decidir. El enlace de esa cobertura se guarda en un campo nuevo y opcional, `coverage_url`, que no se usa al puntuar.
- **Variedad:** no más de la mitad de los casos nuevos sobre Colombia, y al menos tres países distintos. Temas mezclados: política, economía, salud y sucesos.
- **Idioma:** español, como los usuarios de la app.
- **Mixtos:** calificaciones como «Engañoso», «Cuestionable», «Cierto, pero» o «Impreciso». Al menos uno debe ser un dato que **cambió con el tiempo**, que es lo que el veredicto `CHANGED` promete.
- **Inventados:** plausibles y del mismo estilo que los reales, sin nada que los desmienta de forma directa.
- Los casos existentes no se tocan.

### Tope de créditos

`DEFAULT_MAX_CREDITS` pasa de 40 a 60, para que una ejecución completa de 20 casos no se corte por el tope si un caso hace una segunda búsqueda.

### Informe

Se añade a los totales:

- el modo (normal o ciego);
- los aciertos por tipo de caso (`false`, `true`, `mixed` e `invented`);
- los aciertos sin los casos contaminados, como ahora.

## Cómo se sabe que salió bien

- Las pruebas de la evaluación cubren la exclusión de dominios en modo ciego y la carga de `coverage_url`.
- `--dry-run` muestra 20 casos y el coste estimado.
- Con la aprobación del dueño, una ejecución en cada modo (unos 80 créditos). En modo ciego ningún caso sale contaminado. En modo normal se registra cuántos salen limpios, pero no es una condición: un caso nuevo puede quedar contaminado si otro verificador de la lista chequeó lo mismo, y no se quita por eso.
- ESTADO.md registra los dos resultados, el gasto de créditos y la comparación entre modos.

## Lo que queda a criterio de quien lo construya

- Qué casos concretos se eligen, siempre que cumplan los criterios.
- Cómo se pasa la exclusión de dominios al runner (parámetro, función aparte…).
- El formato exacto de las tablas nuevas del informe.
