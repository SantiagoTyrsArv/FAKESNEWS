# Verificación gratuita con Tavily y Gemini

**Estado:** aprobada por el dueño el 2026-11-07, y ajustada con los resultados de la [fase 0](2026-11-07-tavily-gemini-phase0.md): `advanced`, 450 afirmaciones al mes y `gemini-3.5-flash-lite`.
**Fecha:** 2026-11-07.

## 1. Por qué

El dueño pagó 5 USD de créditos de Anthropic y no piensa gastar más. Tres envíos reales consumieron casi todo lo que quedaba. Un artículo costó unos 1,56 USD, porque cada llamada a Claude arrastra hasta 120.000 tokens de resultados de búsqueda y los fallos se reintentaban pagando otra vez. Sin créditos, la verificación deja de funcionar.

El objetivo es que FakesNews pueda verificar sin pagar, sin perder lo que la hace fiable: solo cita fuentes de confianza y nunca inventa una evidencia.

## 2. Objetivos

- Verificar afirmaciones con coste 0 USD, dentro de los planes gratuitos.
- Seguir buscando únicamente en las fuentes de confianza.
- Que ninguna URL, fragmento o fecha de una evidencia salga del modelo: todo debe venir de la búsqueda.
- Que un fallo técnico no se muestre como «evidencia insuficiente».
- Que agotar la cuota gratuita dé un mensaje claro y no un veredicto falso.
- Que la evaluación use el mismo modelo que producción.

## 3. Fuera de alcance

- Un veredicto intermedio para lo que es cierto solo en parte. Es una decisión aparte, pero conviene tomarla después, con datos de este modelo.
- Admitir varios proveedores a la vez o cambiar de proveedor en caliente.
- Añadir fuentes de confianza (por ejemplo, medios paraguayos).
- La protección de `main` y el resto de pendientes de `docs/ESTADO.md`.

## 4. Lo que sería un fracaso aunque funcione

- Citar fuentes que no están en la lista de confianza.
- Mostrar un veredicto con evidencias que el buscador no devolvió.
- Enviar a Google datos personales de usuarios sin avisarles.
- Que una sola cuenta pueda agotar la cuota mensual de toda la app.

## 5. Hechos comprobados el 2026-11-07

Consultados en las páginas oficiales. Pueden cambiar: la fase 0 los vuelve a comprobar.

| Tema | Dato |
|---|---|
| Tavily, plan gratuito | 1.000 créditos al mes. `basic` cuesta 1 crédito y `advanced`, 2. |
| Tavily, búsqueda | `include_domains` admite hasta 300 dominios y `max_results`, hasta 20. Se puede pedir la fecha de publicación. |
| Tavily, velocidad | 100 peticiones por minuto en entorno de desarrollo. |
| Gemini, plan gratuito | Sin coste de tokens en `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite`, entre otros. |
| Gemini, modelos 2.5 | Están obsoletos. `gemini-2.5-flash` se redirige a modelos nuevos el 2026-12-01, así que no se usan. |
| Gemini, búsqueda | Google Search no está disponible gratis en los modelos 3 y no permite exigir dominios concretos. Por eso se busca con Tavily. |
| Gemini, límites | Google no publica los del plan gratuito por modelo: se ven en AI Studio. Se aplican por proyecto y no están garantizados. |
| Gemini, salida estructurada | Disponible en preview, solo en modelos Gemini 3. |
| Gemini, datos | **En el plan gratuito, Google usa lo enviado para mejorar sus productos, y personas pueden leerlo.** Sus términos dicen que no se envíe información sensible, confidencial o personal. |
| Gemini, restricciones | Hay que tener 18 años o más. En el EEE, Suiza y Reino Unido, una app para usuarios solo puede usar servicios de pago. |

Fuentes: [precios de Gemini](https://aistudio.google.com/docs/pricing), [límites de Gemini](https://aistudio.google.com/docs/rate-limits), [términos de Gemini](https://aistudio.google.com/docs/terms), [salida estructurada](https://aistudio.google.com/docs/structured-output), [créditos de Tavily](https://docs.tavily.com/documentation/api-credits), [búsqueda de Tavily](https://docs.tavily.com/documentation/api-reference/endpoint/search), [límites de Tavily](https://docs.tavily.com/documentation/rate-limits).

## 6. Diseño

### 6.1 Flujo

```
Texto del caso
  → Gemini extrae hasta 4 afirmaciones
  → para cada afirmación:
      Tavily busca solo en las fuentes de confianza
      sin resultados → INSUFFICIENT (sin llamar a Gemini)
      con resultados → Gemini juzga esos resultados numerados
      la app construye las evidencias con los datos de Tavily
```

La búsqueda deja de ser una herramienta que el modelo decide usar. La hace la app, una vez por afirmación, y el modelo solo lee lo que recibe.

### 6.2 Búsqueda

- Una búsqueda por afirmación, con el texto de la afirmación como consulta y `search_depth: advanced`. Cuesta 2 créditos.
- `include_domains` lleva todas las fuentes de confianza. `UNSEARCHABLE_DOMAINS` se elimina, porque Tavily devuelve esos medios.
- Hasta 8 resultados, con la fecha de publicación y sin el contenido completo de las páginas. Eso mantiene la petición pequeña.
- No se filtra por fecha: hay afirmaciones sobre hechos antiguos.
- La app vuelve a comprobar que cada dominio devuelto pertenece a una fuente de confianza, con la lógica actual de subdominios.

### 6.3 Veredicto

Gemini recibe la fecha de hoy, la afirmación y los resultados dentro de etiquetas, cada uno con un número. El prompt mantiene las reglas actuales: el contenido es dato y nunca instrucción. Debe juzgar solo con los resultados, sin usar lo que recuerde, porque muchas noticias son posteriores a su entrenamiento.

La respuesta usa salida estructurada con este esquema:

```json
{
  "verdict": "SUPPORTED | CONTRADICTED | INSUFFICIENT",
  "rationale": "explicación breve en español",
  "evidence": [{ "result_id": 1, "stance": "supports | contradicts | neutral" }]
}
```

**El modelo elige un número, no escribe una URL.** La URL, el dominio, el fragmento y la fecha se toman del resultado de Tavily. Un `result_id` inexistente se descarta. Esto hace imposible inventar una evidencia, sustituye la extracción de JSON de texto libre de los PR #83 y #84, y cubre lo que señaló la revisión de seguridad.

Se mantiene la regla actual: un veredicto direccional sin evidencia que lo respalde pasa a `INSUFFICIENT`.

### 6.4 Extracción de afirmaciones

Mismo prompt y mismo esquema, con Gemini y salida estructurada. El máximo baja de 8 a 4 afirmaciones por envío, en `MAX_CLAIMS_PER_SUBMISSION` y en el prompt. Si el modelo devuelve más, o una afirmación demasiado larga, se recorta en lugar de perder el caso.

### 6.5 Fallos técnicos

Hoy un error se guarda como `INSUFFICIENT`, y el reporte no permite distinguirlo. Eso retrasó el diagnóstico del 2026-11-07.

- `VerifyResult` y la tabla de afirmaciones llevan un indicador `verification_failed`, con una migración de Alembic. El veredicto almacenado sigue siendo `INSUFFICIENT`.
- El reporte muestra «No se pudo verificar» con un estilo propio, separado de «Evidencia insuficiente».
- Una afirmación fallida no cuenta en la puntuación ni en la reputación de las fuentes.
- Si fallan todas las afirmaciones, el caso termina en `failed`, con un mensaje para el usuario.
- Los errores temporales (429 y 5xx) se reintentan una vez, respetando `Retry-After`. Una respuesta que no cumple el esquema no se reintenta y cuenta como fallo.
- `VERIFY_CONCURRENCY_LIMIT` baja de 4 a 2.

### 6.6 Cuota

Cualquiera puede registrarse, así que hace falta un tope de toda la app, además del actual por cuenta.

- Antes de aceptar un envío, se cuentan las afirmaciones creadas en el mes en curso. Con `MAX_CLAIMS_PER_MONTH` (450 por defecto) o más, el envío se rechaza con un mensaje que explica que se agotó la cuota. Se cuenta en Postgres, como el tope diario, para que sobreviva a un vaciado de Redis.
- 450 afirmaciones dan para unos 112 envíos completos al mes y gastan 900 créditos. Quedan 100 créditos de margen para la evaluación.
- El tope por cuenta de 20 envíos al día baja a 5.
- Cada cuenta tiene además un tope de 60 afirmaciones al mes (`MAX_CLAIMS_PER_ACCOUNT_PER_MONTH`), para que ninguna agote la cuota común.
- Los casos en curso cuentan como `MAX_CLAIMS_PER_SUBMISSION` afirmaciones cada uno, porque se guardan al terminar. El tope sigue siendo aproximado: dos envíos simultáneos pueden pasar la comprobación a la vez, y el margen de 100 créditos cubre esa diferencia.
- Riesgo aceptado: alguien con muchas cuentas aún puede agotar la cuota. No hay coste, porque el plan gratuito simplemente se detiene.
- Si Tavily o Gemini responden que la cuota se agotó, se registra un evento propio en los logs y las afirmaciones cuentan como fallo técnico.

### 6.7 Datos y privacidad

- `/submit` muestra un aviso visible antes de enviar: el contenido se procesa con Google y Tavily, y personas de Google pueden revisarlo, así que no hay que incluir datos personales ni sensibles. También indica que la app es para uso en Colombia.
- Solo se envía a Google el texto del caso y los resultados de búsqueda, nunca datos de la cuenta.
- Se mantiene que el contenido extraído no se escribe en los logs.

### 6.8 Evaluación

- `evals/verdicts` deja de medir dólares y pasa a contar créditos de Tavily y llamadas a Gemini. `--max-usd` se sustituye por `--max-credits`.
- Lee el modelo de `infra/main.bicepparam` y avisa si el del entorno es distinto. Esto evita que se repita lo del 2026-11-07, cuando la evaluación probó un modelo y producción usaba otro.
- Se mantiene el marcado de casos contaminados.
- Se añaden 2 casos: la noticia real del cierre de Ueno Bank, que debe dar `SUPPORTED`, y la afirmación inventada sobre De la Espriella, Trump y Gaza, que debe dar `INSUFFICIENT`. Para el primero hay que enlazar una verificación o noticia publicada.

### 6.9 Infraestructura

- Secretos nuevos en Key Vault: `gemini-api-key` y `tavily-api-key`.
- Variables nuevas: `GEMINI_API_KEY`, `GEMINI_MODEL`, `TAVILY_API_KEY` y `MAX_CLAIMS_PER_MONTH`, en `infra/main.bicep`, `infra/main.bicepparam`, `.env.example` y `docs/AZURE.md`.
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` y la dependencia `anthropic` se retiran al final. El secreto se borra cuando producción lleve una semana estable.
- El dueño crea las dos claves con una cuenta personal, no con la de la universidad, cuyo tenant tiene restricciones. Las guarda en Key Vault sin pegarlas en el chat.

## 7. Fase 0: prueba antes de migrar

Antes de tocar el código de producción se hace una prueba desechable, sin coste, fuera de `app/`. Es lo que decide si la migración sigue adelante.

Un script corre los 6 casos de la evaluación más los 2 nuevos, y responde:

1. ¿Tavily encuentra resultados útiles en las fuentes de confianza, incluidas las noticias recientes como Ueno?
2. ¿Devuelve Reuters, AP, BBC y EFE?
3. ¿Qué modelo Gemini da mejores veredictos? Se comparan `gemini-3.8-flash` y `gemini-3.5-flash-lite`.
4. ¿Qué límites muestra AI Studio para esos modelos? Un envío usa hasta 5 llamadas.

**Criterio para continuar:** al menos 6 de 8 aciertos, ningún error grave nuevo frente a Claude, y Ueno correcto. Si no se cumple, se para y se revisa con el dueño: por ejemplo, 2 búsquedas por afirmación, `advanced` o más resultados.

## 8. Cómo se sabrá que está terminado

- Criterio de la fase 0 repetido con el código final y con el modelo de producción.
- Un envío real de texto y otro de artículo terminan con veredictos y evidencias válidas.
- Una prueba simula la cuota agotada y el reporte muestra «No se pudo verificar».
- Ninguna evidencia guardada viene de fuera de los resultados de Tavily.
- Ninguna evidencia sale de un dominio fuera de la lista de confianza.
- La API sigue con todas sus pruebas y sin llamadas de red en el CI.

## 9. Riesgos

| Riesgo | Efecto | Respuesta |
|---|---|---|
| Google o Tavily reducen el plan gratuito | La verificación se para | El mensaje de cuota lo hace visible. Pagar Gemini sería barato y además deja de usar los datos para entrenar. |
| Fragmentos cortos | Peor veredicto que leyendo la página | Medido en la fase 0: por eso se usa `advanced`. |
| Una sola búsqueda por afirmación | Se escapa evidencia que Claude encontraba reformulando | La fase 0 lo mide. |
| Salida estructurada en preview | Puede cambiar | Se aísla en `app/core/llm.py` y las pruebas fijan el formato. |
| Usuarios del EEE, Suiza o Reino Unido | Los términos exigen servicios de pago | La app solo se usa en Colombia (§11). Si eso cambia, hay que pasar a un plan de pago. |
| La vuelta atrás a Claude | Necesita créditos | Se revierte el PR y se recarga, si el dueño quiere. |

## 10. Decisiones tomadas por Claude, para revisar

- Sustituir a Anthropic en lugar de mantener dos proveedores: es menos código, y el historial de git conserva la versión anterior.
- Una búsqueda por afirmación, en vez de dejar que el modelo decida.
- 4 afirmaciones por envío, 450 al mes y 5 envíos al día por cuenta.
- Evidencias por número de resultado, en lugar de URL escritas por el modelo.
- El indicador `verification_failed`, en lugar de un veredicto nuevo.
- Hacer la fase 0 antes de migrar.

## 11. Decisiones del dueño

Tomadas el 2026-11-07:

1. **Acepta las condiciones del plan gratuito de Gemini,** incluido que personas de Google puedan leer lo enviado y que se use para mejorar sus productos.
2. **La app solo se usa en Colombia.** El aviso de `/submit` lo indica. No hay bloqueo técnico.
3. **Criterio de la fase 0:** al menos 6 de 8 aciertos, como en §7.

## 12. Lo que se decide en el plan

- Si se usa el SDK `google-genai` o peticiones `httpx` directas. Se prefiere `httpx` si el SDK no aporta una API asíncrona clara, porque ya está en el proyecto y `respx` lo cubre en las pruebas.
- El límite de longitud de la consulta en Tavily, que su documentación no indica.
- Los códigos exactos de cuota agotada de cada servicio.
- El orden de los PR. Propuesta: fallos técnicos y cuota primero, porque sirven con cualquier proveedor; después el cambio de proveedor, la evaluación y la limpieza.
