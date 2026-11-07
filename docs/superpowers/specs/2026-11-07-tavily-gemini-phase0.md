# Fase 0 de la migración a Tavily y Gemini: resultados

**Fecha:** 2026-11-07. **Resultado:** criterio superado, la migración continúa.

Prueba desechable con los 6 casos de la evaluación, la noticia real de Ueno Bank y una afirmación inventada sobre De la Espriella, Trump y Gaza.

| Configuración | Aciertos | Errores graves |
|---|---|---|
| Claude (`claude-sonnet-5-5`), solo 6 casos | 5 de 6 | 1 |
| `gemini-3.5-flash-lite`, búsqueda `basic` | 5 de 8 | 1 |
| **`gemini-3.5-flash-lite`, búsqueda `advanced`, plan gratuito** | **7 de 8** | **0** |
| `gemini-3.8-flash` | No medible | 503 y tiempos de espera |
| `gemini-3.5-flash` y `gemini-3.6-flash` | No medibles | Proyecto sin saldo |

El criterio era al menos 6 de 8, ningún error grave nuevo frente a Claude y Ueno correcto.

## Decisiones

- **Modelo:** `gemini-3.5-flash-lite`.
- **Búsqueda:** `search_depth: advanced`, a 2 créditos. Con `basic`, los fragmentos no alcanzaban.
- **Cuota:** `MAX_CLAIMS_PER_MONTH` baja de 900 a 450. El dueño lo aceptó.
- **Fuentes:** Tavily devuelve Reuters, AP, EFE y BBC, así que `UNSEARCHABLE_DOMAINS` se elimina.

## Datos técnicos

- Petición válida: `POST /v1beta/models/{model}:generateContent`, con cabecera `x-goog-api-key` y `generationConfig.responseMimeType` más `responseJsonSchema`.
- Cada veredicto usó entre 2.500 y 4.700 tokens, y las 8 llamadas con pausas de 5 s no dieron 429.
- Un proyecto de prepago sin saldo responde `402` con estado `RESOURCE_EXHAUSTED`, también en los modelos gratuitos. **El plan gratuito exige un proyecto sin facturación.**
- `gemini-3.8-flash` respondió 503 («high demand») y tiempos de espera largos.

## Límites de esta prueba

- 2 de los 7 aciertos están contaminados: `co-falso-1` y `co-falso-2` citaron la verificación del propio fact-checker.
- La afirmación inventada salió `CONTRADICTED` en lugar de `INSUFFICIENT`: el modelo tomó encuentros reales como si desmintieran la afirmación. Es un fallo leve, y la evaluación lo sigue midiendo.
- Son solo 8 casos, y no se midió el límite diario del plan gratuito, que Google no publica. El código debe tratar el agotamiento de cuota como fallo técnico.
- El límite de longitud de la consulta y el código de cuota agotada de Tavily quedan por comprobar en la tarea 5.
