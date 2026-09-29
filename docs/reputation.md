# Perfil de confiabilidad de fuentes

Este documento explica la fórmula usada por `apps/api/app/modules/sources/reputation.py`
para puntuar fuentes, sus supuestos, y sus limitaciones conocidas — en particular una
posible circularidad y un sesgo de conformismo, que son consecuencias directas del diseño
y no bugs a corregir en el MVP, pero sí algo que cualquiera que lea los scores debe entender.

## Modelo: Beta-Bernoulli

Cada fuente tiene dos parámetros, `alpha` y `beta`, que representan los parámetros de una
distribución Beta sobre "¿con qué probabilidad esta fuente coincide con el consenso cuando
toma una postura verificable?". Cada vez que una fuente participa en la verificación de una
afirmación (ver más abajo qué cuenta como "participar"):

- Si su postura coincide con el consenso ponderado → **hit**: `alpha += 1`.
- Si su postura difiere del consenso → **miss**: `beta += 1`.

El **score** reportado es simplemente la media de la posterior:

```
score = alpha / (alpha + beta)
```

### Priors iniciales

Los valores iniciales de `alpha`/`beta` vienen de `app/data/trusted_sources.json`
(`prior_alpha`, `prior_beta`), definidos por tipo de fuente al sembrar la base
(`sources/seed_loader.py`). Por ejemplo, organismos oficiales (`oficial`) arrancan con un
prior más optimista (p. ej. 9/1) que medios genéricos (p. ej. 6/2), reflejando una
expectativa inicial razonable, no un juicio definitivo — la posterior se actualiza con
evidencia real a medida que el sistema opera.

### Intervalo aproximado

`compute_score_interval` devuelve un intervalo usando la **aproximación normal** a la
Beta(alpha, beta): `media ± 1.96 * desviación_estándar`, recortado a `[0, 1]`. Es una
aproximación (no el cuantil exacto de la Beta) — funciona bien como una señal visual de
"cuánta confianza depositar en este número", no para inferencia estadística rigurosa.

### Bandera de muestra pequeña

`cases_count < 10` marca `low_sample = true`. Con pocos casos, el score puede ser volátil
incluso con el piso de peso mínimo (ver abajo) — la bandera es una señal para la UI, no un
ajuste al cálculo del score en sí.

## ¿Cuándo se puntúa una fuente?

Al terminar `verify` para una afirmación, `sources/reputation.py` decide si actualizar
reputación siguiendo estas reglas, en orden:

1. **El veredicto de la afirmación no puede ser `INSUFFICIENT`.** Sin veredicto claro no
   hay nada que puntuar.
2. **Solo cuenta evidencia direccional** (`stance` = `supports` o `contradicts`).
   La evidencia `neutral` no participa ni en el conteo de independencia ni en el consenso.
3. **Deduplicación por independencia**: las fuentes que comparten `syndication_group`
   (p. ej. varios medios republicando el mismo cable de una agencia) cuentan como **una
   sola voz independiente**, tanto para el umbral mínimo como para el voto ponderado de
   consenso. Una fuente sin `syndication_group` es su propia voz independiente.
4. **Mínimo 2 fuentes independientes.** Si tras la deduplicación queda menos de 2 grupos
   independientes, no se puntúa nada para esa afirmación.
5. **Consenso ponderado**: cada grupo independiente aporta un voto de `+1` (supports) o
   `-1` (contradicts), multiplicado por un peso = `max(score_actual_de_la_fuente, 0.05)`
   (el piso de 0.05 evita que una fuente con score cercano a 0 quede con peso ~0 y sea
   efectivamente invisible para el consenso). Se suman los votos ponderados; el signo del
   resultado define el consenso (`supports` si es positivo, `contradicts` si es negativo).
   Un empate exacto (suma = 0) no produce actualización — no hay un consenso claro con el
   que comparar.
6. **Puntuación individual**: cada fuente que aportó evidencia direccional (no solo la
   representante de cada grupo sindicado) recibe su propio hit/miss comparando *su*
   postura contra el consenso ya calculado. Es decir, la deduplicación por sindicación
   afecta cómo se calcula el consenso, pero cada fuente individual sigue acumulando su
   propio historial.

## Idempotencia

Cada actualización inserta una fila en `source_score_events` con una restricción única en
`(source_id, claim_id)`. Antes de puntuar una fuente para una afirmación, se verifica si ya
existe una fila para ese par; si existe, se omite. Esto permite reprocesar una afirmación
(o volver a llamar a la función por error) sin inflar artificialmente el `alpha`/`beta` de
una fuente. Toda la actualización (evento + incremento de `alpha`/`beta`/`cases_count`) se
hace en una única transacción.

## Limitaciones conocidas (léase antes de confiar en los números)

### 1. Circularidad

El peso de cada fuente en el cálculo del consenso es **su propio score actual**. Esto
significa que las fuentes con score alto pesan más al determinar cuál es "el consenso" —
y luego son recompensadas precisamente por coincidir con el consenso que ayudaron a
formar. Un prior inicial sesgado (o un score que se desvía por azar en los primeros casos)
tiende a **autoreforzarse** en vez de corregirse solo, porque el mecanismo de puntuación no
es independiente del mecanismo que asigna pesos.

### 2. Sesgo de conformismo

El sistema mide **consenso entre fuentes**, no verdad objetiva. Una fuente que reporta
correctamente algo minoritario pero fácticamente cierto — mientras que la mayoría ponderada
(dominada por fuentes de score alto) se equivoca — será penalizada (`miss`) por discrepar,
no por estar equivocada. No hay forma de que este sistema, por diseño, distinga "la fuente
disidente tenía razón" de "la fuente disidente estaba equivocada": ambas producen el mismo
resultado (miss) si el consenso ponderado va en la otra dirección.

### 3. El consenso no es el veredicto del LLM

El `verdict` (`SUPPORTED`/`CONTRADICTED`) que ve el usuario en el reporte lo determina el
LLM en `pipeline/verify.py` interpretando la evidencia. El "consenso" que usa
`reputation.py` para puntuar fuentes es un cálculo **separado**, basado únicamente en las
posturas (`stance`) reportadas por cada fuente. Es posible — aunque no lo esperado en el
caso típico — que ambos diverjan.

### 4. Ventana de evidencia limitada

La reputación solo se actualiza con la evidencia que `verify.py` decidió incluir en su
respuesta para una afirmación puntual (limitada por `max_uses` de la búsqueda). No es un
muestreo exhaustivo de todo lo que existe sobre el tema, así que el "consenso" está acotado
por lo que el LLM encontró y decidió citar en esa corrida.

## Qué NO intenta resolver este diseño

- No pretende ser un sistema de fact-checking objetivo: es una heurística de consistencia
  entre fuentes, pensada como una señal más dentro del reporte, nunca como la única.
- No corrige sesgos ideológicos o editoriales compartidos por múltiples fuentes no
  sindicadas pero alineadas (dos medios independientes en lo corporativo pueden compartir
  el mismo sesgo sin que `syndication_group` lo capture).
- No pondera por calidad del argumento o rigor periodístico de una pieza individual, solo
  por la postura reportada y el historial agregado de la fuente.
