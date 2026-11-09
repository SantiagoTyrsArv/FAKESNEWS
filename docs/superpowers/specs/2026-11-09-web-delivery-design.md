# Diseño: WebSockets, patrones de renderizado, INP y cierre de sesión entre pestañas

Fecha: 2026-11-09. Estado: borrador, pendiente de aprobación.

## Para qué

Es una entrega de la materia de Programación Web. El profesor la evalúa de dos formas:

1. **Una demostración en vivo** sobre https://fakesnews.vercel.app (producción: web en Vercel y API en Azure Container Apps).
2. **Un agente que revisa el repositorio** y comprueba que cada requisito está en el código.

Así que cada pieza tiene que **funcionar en producción** y **ser fácil de encontrar en el código**: nombres claros, comentarios que digan qué requisito cubre cada cosa y un documento que lo explique todo.

Los cuatro requisitos:

1. WebSockets en lugar del sondeo (polling) en la página del informe.
2. Patrones de renderizado: CSR, SSR, SSG, ISR y streaming, con ejemplos del propio proyecto y un documento comparativo.
3. INP con `useReportWebVitals`, junto con LCP y CLS, enviados a la API y guardados en los logs de Azure.
4. (Extra) `BroadcastChannel` para cerrar la sesión en todas las pestañas a la vez.

## Objetivos

- Que en la demo en vivo se vea cada cosa funcionando: la barra de progreso avanza sin esperar al siguiente sondeo, `/sources` sale de la caché, `/reports/[id]` llega por streaming, las métricas aparecen en los logs de Azure y cerrar sesión en una pestaña cierra las demás.
- Que el agente que revise el código encuentre cada requisito en un sitio evidente y documentado.
- Que nada de lo que hoy funciona empeore: si falla el WebSocket, se vuelve al sondeo; si falla el SSR, se pasa a CSR.

## Fuera de alcance

- Cambiar la autenticación de la web o el dominio de la API.
- Usar WebSockets en otras páginas que no sean `/reports/[id]`.
- Montar un panel de métricas: basta con que queden en los logs y se puedan consultar con KQL.
- Dependencias nuevas en la web: `useReportWebVitals` y `BroadcastChannel` ya vienen incluidos. En la API hay que comprobar si `uvicorn[standard]` ya trae `websockets` y no añadir nada que no haga falta.

## Lo que no puede pasar

- Que la seguridad empeore. El WebSocket tiene que validar `Origin` (contra CSWSH) y comprobar que el caso es del usuario. El ticket es de un solo uso y caduca en poco tiempo. El endpoint de métricas no puede servir para inundar los logs.
- Que la página del informe se quede colgada si la API está apagada (escala a cero): en ese caso manda el sondeo.
- Que la landing deje de ser estática o que empeore el Lighthouse móvil (mediana de PSI 97).

## Situación actual (comprobada en el código)

- `apps/web/app/reports/[id]/report-client.tsx`: componente de cliente que consulta `getSubmission(id)` cada 2 s (`POLL_INTERVAL_MS`). Deja de consultar a los 16 min (`STALE_AFTER_MS`) y, cuando el estado es `done`, pide el informe completo.
- `apps/api/app/modules/pipeline/orchestrator.py`: `_set_status(db, submission, new_status, error=...)` cambia el estado y hace commit. **No es el único sitio:** `_mark_failed` (línea 99, con su propia sesión) y `submissions/service.py:195` también ponen `status = "failed"` directamente. Los tres tienen que publicar el evento.
- Estados: `SubmissionStatus` en `apps/api/app/modules/submissions/schemas.py`. Tipos de entrada: `text`, `url` y `video`.
- Redis ya está disponible en la API (`app/core/rate_limit.py:get_redis()`, `redis.asyncio`, `decode_responses=True`) y en el worker (arq, `app/core/queue.py`). El orquestador corre en el worker, y el endpoint WebSocket corre en la API, que es otro contenedor. Redis pub/sub los conecta.
- Autenticación: la cookie `access_token` (`httponly`, `samesite=lax`, `path=/`) la lee `get_current_user` en `app/core/deps.py`. Las peticiones de la web que cambian datos llevan además CSRF de doble envío (`require_csrf`: cookie `csrf_token` y cabecera `X-CSRF-Token`).
- La web llega a la API a través del proxy `/api` (`apps/web/proxy.ts`, `API_PROXY_TARGET` y `NEXT_PUBLIC_API_URL=/api`). La cookie es de `fakesnews.vercel.app`. **El proxy de Vercel no deja pasar WebSockets**, y como `vercel.app` es un sufijo público, la cookie no se puede compartir con otro dominio. La API acepta conexiones directas: `X-Proxy-Secret` solo se usa para saber la IP real del cliente (`client_ip.py`) y no bloquea nada.
- CORS: `CORSMiddleware` en `app/main.py`, con los orígenes de `CORS_ORIGINS`.
- CSP: `apps/web/lib/csp.mjs` (`buildCsp({ dev, apiUrl })`). Su `connect-src` solo admite `'self'` y el origen de la API cuando es una URL absoluta. Las pruebas están en `lib/csp.test.mjs`.
- `/sources`: `page.tsx` (servidor, solo metadatos) y `sources-client.tsx` (cliente, `apiFetch("/sources")` en un `useEffect`, además de cosas que dependen de la sesión, como `readCsrfCookie`). La API manda `Cache-Control: public, max-age=60` en los `GET` de `_CACHEABLE_PREFIXES` (`app/core/middleware.py:61`). Comprobado.
- `/reports/[id]`: `page.tsx` (servidor) renderiza `<ReportClient params>`. Hoy todo es CSR.
- Métricas: la app no mide nada todavía. El LCP y el CLS salen de Lighthouse y PSI.
- Cierre de sesión: `logout()` en `apps/web/lib/auth.ts:100`, que se llama desde `components/site-header.tsx`.
- La versión de Next de este repositorio cambia APIs respecto a versiones anteriores. `apps/web/AGENTS.md` pide leer la guía en `node_modules/next/dist/docs/` antes de escribir código, sobre todo lo que toca `revalidate`, `cookies()`, streaming y `useReportWebVitals`.

## 1. WebSockets

### Decidido con el dueño

- El WebSocket es real y funciona en producción. Se descartó la opción de dejarlo solo en local.
- Como la cookie no llega a la API en Azure, se usa un **ticket**, y es la cookie la que autentica la petición del ticket. El dueño lo aceptó porque sigue siendo una implementación real de WebSockets.

### Flujo

1. **Pedir el ticket.** `POST /submissions/{id}/ws-ticket`, a través del proxy `/api`. Pasa por `get_current_user` (la cookie `httpOnly`) y por `require_csrf`, y comprueba que el caso es del usuario (si no, 404, igual que `GET /submissions/{id}`). Genera un token aleatorio (`secrets.token_urlsafe(32)`) y lo guarda en Redis como `ws-ticket:{token}` con el valor `{user_id}:{submission_id}` y un TTL de 30 s. Responde `{ "ticket": "...", "expires_in": 30 }`. Tiene límite de peticiones, como las demás rutas de escritura.
2. **Abrir la conexión.** El navegador abre `new WebSocket(`${NEXT_PUBLIC_WS_URL}/ws/submissions/${id}?ticket=${ticket}`)` directamente contra la API. En producción será algo como `wss://ca-fakesnews-api.<env>.azurecontainerapps.io`; en local, `ws://localhost:8000`.
3. **Endpoint `@router.websocket("/ws/submissions/{submission_id}")`**, en un router nuevo o en el de envíos. Hace las comprobaciones en este orden y, si alguna falla, cierra **antes de `accept()`**, o justo después con un código de cierre de aplicación:
   1. **`Origin`:** tiene que estar en la lista de orígenes permitidos, que es la misma de `CORS_ORIGINS`. Si falta o no coincide, cierra (código 1008). Esto protege contra CSWSH.
   2. **Ticket:** lo consume de forma atómica (`GETDEL`). Si no existe o caducó, cierra (1008).
   3. **Caso:** el `submission_id` del ticket tiene que coincidir con el de la ruta y pertenecer al `user_id` del ticket. Se vuelve a comprobar en la base de datos.
   4. `accept()`. Lo primero que envía es el estado actual del caso (`{"status": ..., "error": ...}`), para que el cliente no se pierda ningún cambio ocurrido entre el ticket y la conexión.
   5. Se suscribe a `submission:{id}` y reenvía cada mensaje como JSON.
   6. Cierra el socket cuando llega un estado terminal (`done` o `failed`), cuando el cliente se desconecta o cuando pasa un tiempo máximo (el mismo margen que `STALE_AFTER_MS`). Siempre se da de baja del canal y suelta la conexión de pub/sub.
4. **Publicación.** Una función, por ejemplo `publish_status(submission_id, status, error)`, publica en `submission:{id}` el JSON `{"status": ..., "error": ...}` después de cada commit de estado. La llaman `_set_status`, `_mark_failed` y el `status = "failed"` de `submissions/service.py`. Si Redis falla, se registra un aviso y se sigue: **un fallo al publicar nunca hace fallar el pipeline**, porque el sondeo cubre el hueco.

### Cliente (`report-client.tsx`)

- Si el caso no está en un estado terminal, pide el ticket y abre el WebSocket. Con cada mensaje actualiza `submission.status` y `PipelineProgress`. Con `done`, pide el informe completo, igual que ahora.
- **Vuelta al sondeo:** si no hay `NEXT_PUBLIC_WS_URL`, si falla el ticket, si la conexión no se abre en unos segundos (la API puede estar arrancando desde cero), o si se cierra antes de un estado terminal, se usa el sondeo actual. Ese código sigue ahí como respaldo, no se borra.
- Se mantiene `STALE_AFTER_MS`, y se cierra el socket al salir de la página.
- Conviene que la lógica del socket esté en un hook o módulo con nombre claro (por ejemplo `lib/submission-socket.ts` o `useSubmissionSocket`), con pruebas en Vitest como las de `apiFetch`.

### CSP y configuración

- `buildCsp` admite el origen del WebSocket (`wss://…` o `ws://…`) en `connect-src`. El origen sale de `NEXT_PUBLIC_WS_URL`. Hay pruebas nuevas en `csp.test.mjs`.
- Web: la variable nueva `NEXT_PUBLIC_WS_URL` va en `.env.example` y en Vercel (producción y preview).
- API: el ingress de Container Apps admite WebSockets sobre HTTPS, pero hay que comprobarlo en `infra/modules/api.bicep`. Si hace falta un ajuste, se hace en el Bicep y no a mano.
- **Lo hace el dueño:** añadir la variable en Vercel, si el builder no tiene acceso. Si la conexión tarda en llegar, no pasa nada: la web sigue con el sondeo.

## 2. Patrones de renderizado

| Ruta | Patrón | Cómo |
|---|---|---|
| `/` (landing) | SSG | Sin cambios |
| `/sources` | ISR | `export const revalidate = 60`, igual que el `Cache-Control` de 60 s de la API. Un componente de servidor pide `/sources` a la API (`API_PROXY_TARGET`, desde el servidor) y pasa los datos a `SourcesClient`, que conserva lo interactivo y lo que depende de la sesión |
| `/reports/[id]` | SSR con streaming | El componente de servidor lee la cookie con `cookies()`, pide el caso a la API y envía primero la cabecera. El contenido va dentro de `<Suspense fallback=…>`. El cliente se hidrata con esos datos y, si el caso sigue en proceso, abre el WebSocket |
| `/history`, `/submit`, `/settings`, `/login`, `/register` | CSR | Sin cambios. El documento los usa como ejemplos de CSR |

Detalles:

- **`/sources` con ISR:** si la API falla al generar o regenerar la página (por ejemplo, porque está apagada), no se puede publicar una página rota. Lo deseable es mantener la última versión buena. Si no se pudo generar nunca, el cliente pide los datos como ahora. El dato se pide desde el servidor de Next, no a través de `/api`.
- **`/reports/[id]` con SSR:** si la API responde 401 (por ejemplo, porque el access token caducó, ya que el servidor no puede renovarlo), 404 o un error, se pasa al `ReportClient` actual, que pide los datos y renueva la sesión en el navegador. El 404 se sigue mostrando como ahora. A la API se le envían solo las cookies que necesita.
- **Documento `docs/RENDERIZADO.md`**, en español, como el resto de `docs/`:
  - qué es cada patrón (CSR, SSR, SSG, ISR y streaming), cuándo usarlo y qué cuesta;
  - una tabla con qué ruta del proyecto usa cada uno, con enlace al archivo y la línea;
  - **cómo comprobarlo en vivo**: la cabecera `x-vercel-cache` y su `HIT`/`STALE` en `/sources`, el HTML que llega por partes en `/reports/[id]` (por ejemplo, con `curl -N`), la landing servida estática y la vista de red con el WebSocket (`101 Switching Protocols`);
  - y en qué parte del flujo entra el WebSocket.

## 3. Métricas web: INP, LCP y CLS

### Decidido con el dueño

Las métricas se envían a la API y quedan en los logs de Azure. No basta con mostrarlas en la consola.

### Diseño

- **Web:** un componente de cliente (por ejemplo `components/web-vitals.tsx`) usa `useReportWebVitals` y va montado en `app/layout.tsx`. Envía **INP, LCP y CLS**. Si es gratis, también TTFB y FCP. Cada métrica se manda con `navigator.sendBeacon('/api/vitals', …)` y, si no hay `sendBeacon`, con `fetch(..., { keepalive: true })`. El cuerpo es pequeño: `name`, `value`, `rating`, `id`, `navigationType` y la ruta **sin** query ni id (`/reports/[id]`, no la URL real).
- **API: `POST /vitals`**
  - No pide sesión: las métricas también llegan desde la landing sin iniciar sesión.
  - **Sin CSRF:** `sendBeacon` no puede añadir cabeceras. Se compensa con el resto: valida con Pydantic, con una lista cerrada de `name`, rangos razonables de `value` y una longitud máxima de la ruta; tiene un límite de peticiones por IP (`rate_limit.py`); y solo escribe en el log, sin efectos secundarios.
  - Registra un evento estructurado, `logger.info("web_vital", name=..., value=..., rating=..., route=...)`, sin IP ni datos personales más allá de lo que ya registra la API.
  - Responde 204.
- **Documentación:** una consulta KQL de ejemplo (`ContainerAppConsoleLogs_CL`, filtrando `web_vital`) en `docs/AZURE.md#observabilidad` o en `RENDERIZADO.md`, para enseñarla en la demo. Hay que comprobar que la alerta `alert-fakesnews-errors` no salta con estos eventos, porque son `info`.

## 4. Cierre de sesión entre pestañas (extra)

- Un módulo (por ejemplo `lib/auth-channel.ts`) con `BroadcastChannel("fakesnews-auth")`. Al terminar `logout()` envía `{ type: "logout" }`.
- Lo escucha algo que esté siempre montado (el `site-header` o un proveedor en el layout). Al recibir el mensaje, pone el estado de la cabecera como «sin sesión» y, si la ruta es privada, lleva a `/login`.
- Si el navegador no tiene `BroadcastChannel`, no se hace nada y no se rompe nada.
- Pruebas en Vitest para el módulo.
- El requisito habla de «postMessage». `BroadcastChannel.postMessage` es justo esa API, y el documento puede decirlo.

## Pruebas y comprobación

- API (`pytest`):
  - ticket: se crea, caduca, no se puede reutilizar y no sirve para el caso de otro usuario;
  - WebSocket con `TestClient.websocket_connect`: rechaza un `Origin` inválido, un ticket inválido o el caso de otro usuario; manda el estado inicial y reenvía lo publicado;
  - se publica en las tres rutas de cambio de estado;
  - `/vitals`: valida la entrada y respeta el límite de peticiones.
- Web: Vitest para `buildCsp`, el módulo del socket (con vuelta al sondeo) y el canal de autenticación. Hay que mantener en verde `pnpm lint`, Stylelint, `tsc` y el build, y el e2e de Playwright del flujo principal.
- En producción, después de fusionar:
  - abrir un caso real y ver el `101` y los mensajes en DevTools;
  - comprobar `x-vercel-cache` en `/sources`;
  - ver el streaming en `/reports/[id]`;
  - ver `web_vital` en Log Analytics;
  - cerrar sesión con dos pestañas abiertas.
- Lighthouse móvil en la landing: que no baje.

## Orden y forma de entrega

Son cuatro partes independientes. Se sugiere un PR por parte, en este orden: **1. WebSockets** (es la mayor y la que más se ve en la demo), **3. métricas**, **4. BroadcastChannel** y **2. renderizado**. El documento `RENDERIZADO.md` va en el último PR, porque describe el estado final.

## Lo que queda a criterio del builder

- Los nombres de archivos, módulos y hooks (los de arriba son sugerencias).
- Si el ticket y el WebSocket van en el router de envíos o en uno propio.
- Los códigos de cierre concretos, siempre que estén documentados.
- La forma del estado de carga del `<Suspense>`, siempre que use los componentes existentes (`LoadingLine`).
- Si se añaden TTFB y FCP a las métricas.
