# Plan de implementación: WebSockets, renderizado, INP y cierre de sesión entre pestañas

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** cumplir los cuatro requisitos de la entrega de Programación Web (WebSockets, patrones de renderizado, INP y `BroadcastChannel`) de forma que funcionen en vivo en producción y se encuentren fácilmente en el código.

**Arquitectura:** el worker publica cada cambio de estado de un caso en Redis pub/sub (`submission:{id}`). La API lo reenvía por un WebSocket directo (`wss://<api>/ws/submissions/{id}`), autenticado con un ticket de un solo uso que se pide a través del proxy `/api` con la cookie `httpOnly`. La web lo usa en `/reports/[id]` y vuelve al sondeo si algo falla. Además: `/sources` pasa a ISR y `/reports/[id]` a SSR con streaming; las métricas web viajan con `sendBeacon` a `POST /vitals`, que las escribe en el log; y el cierre de sesión se propaga con `BroadcastChannel`.

**Stack:** FastAPI + redis.asyncio + pytest (API); Next 16.4.5 (App Router, sin `cacheComponents`), React, Vitest + MSW (web).

**Spec:** `docs/superpowers/specs/2026-11-09-web-delivery-design.md`. Léelo antes de empezar: este plan lo da por leído.

## Restricciones globales

- **La web no lleva dependencias nuevas.** `useReportWebVitals` viene de `next/web-vitals` y `BroadcastChannel` es nativo. En la API, `uvicorn[standard]` ya trae `websockets`: compruébalo con `uv run python -c "import websockets"` y no añadas nada.
- Next 16.4.5 cambia APIs: **antes de escribir código de Next, lee** `apps/web/node_modules/next/dist/docs/01-app/03-api-reference/04-functions/use-report-web-vitals.md`, `.../02-guides/incremental-static-regeneration.md`, `.../01-getting-started/06-fetching-data.md` (streaming y `<Suspense>`) y la referencia de `cookies()`.
- Los textos de la interfaz van en español. Los comentarios del código van en inglés, como el resto del repositorio, y dicen qué requisito cubren (por ejemplo `// Requirement: WebSockets — ...`), para que el agente que revise el código los encuentre. Los documentos de `docs/` van en español.
- Hay un PR por parte, en este orden: **(A) WebSockets** (tareas 1 a 6), **(B) métricas** (7 y 8), **(C) `BroadcastChannel`** (9) y **(D) renderizado** (10 a 12). Cada uno sale de `main`, en una rama `feat/…`, y se fusiona cuando CI y Sonar están en verde.
- Los commits siguen el estilo del repositorio (`feat(api): …`, en español) y terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Los PR terminan con `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- Valores fijados: ticket con un TTL de **30 s**, de un solo uso (`GETDEL`) y guardado en la clave `ws-ticket:{token}`. Canal `submission:{id}`. Mensaje `{"status": str, "error": str | null}`. Vida máxima del socket: **16 min**, igual que `STALE_AFTER_MS`. Código de cierre **1008** para un `Origin`, un ticket o un caso inválidos. `revalidate = 60` en `/sources`. Canal de autenticación `"fakesnews-auth"` con el mensaje `{ type: "logout" }`. Métricas: `CLS`, `FCP`, `INP`, `LCP` y `TTFB`.
- Producción: el FQDN de la API es `ca-fakesnews-api.proudpebble-539cdba7.northcentralus.azurecontainerapps.io`, y `CORS_ORIGINS` es `["https://fakesnews.vercel.app"]` (en `infra/main.bicepparam`). El ingress ya tiene `transport: 'auto'`, que admite WebSockets.

## Puntos que revisar (no los cubre ninguna prueba de tarea)

1. **La API está apagada (escala a cero)** y el WebSocket tarda en abrir: la página tiene que pasar al sondeo en 5 s sin quedarse colgada. Se fija con una prueba en la tarea 5.
2. **Un ticket reutilizado** (repetido o filtrado en un log): la segunda conexión se rechaza. Se fija con una prueba en la tarea 3.
3. **Un cambio de estado entre el ticket y la suscripción:** no se puede perder. El endpoint se suscribe **antes** de leer y enviar el estado actual. Se fija con una prueba en la tarea 3.
4. **La API se reinicia en medio de un caso** (un despliegue) y el socket se cierra antes de un estado terminal: la página tiene que volver al sondeo. Se fija con una prueba en la tarea 5.
5. **Un beacon malformado o enorme en `/vitals`:** se rechaza sin escribir en el log. Se fija con una prueba en la tarea 7.

---

## PR A: WebSockets

### Tarea 1: publicar cada cambio de estado en Redis

**Archivos:**
- Crear: `apps/api/app/modules/submissions/events.py`
- Modificar: `apps/api/app/modules/pipeline/orchestrator.py`, en `_set_status` (l. 41-47) y `_mark_failed` (l. 93-101)
- Modificar: `apps/api/app/modules/submissions/service.py`, en el fallo al encolar (l. 192-197)
- Modificar: `apps/api/tests/conftest.py`, para añadir `publish`, `getdel` y `pubsub()` a `FakeRedis`
- Prueba: `apps/api/tests/submissions/test_events.py`

**Interfaces:**
- Produce `channel_name(submission_id: uuid.UUID | str) -> str`, que devuelve `"submission:{id}"`.
- Produce `async publish_status(submission_id: uuid.UUID | str, status: str, error: str | None, *, client: redis.Redis | None = None) -> None`. Usa `client or get_redis()` (de `app.core.rate_limit`) y publica `json.dumps({"status": status, "error": error})`. Captura `RedisError` y `OSError`, registra `logger.warning("submission_event_publish_failed", submission_id=..., error=str(exc))` y **nunca lanza excepciones**.
- Produce, en `FakeRedis`: `async publish(channel, message) -> int`, `async getdel(key) -> str | None` y `pubsub() -> FakePubSub`. `FakePubSub` tiene `async subscribe(*channels)`, `async unsubscribe(*channels)`, `async get_message(ignore_subscribe_messages: bool = False, timeout: float = 0.0) -> dict | None`, que devuelve `{"type": "message", "channel": ..., "data": ...}` o `None` cuando se agota `timeout`, y `async aclose()`. Usa una `asyncio.Queue` por suscriptor, creada en `subscribe`.

- [ ] **Paso 1: escribir las pruebas que fallan** en `test_events.py`:
  - `test_publish_status_sends_json_on_the_case_channel`: se suscribe con `fake_redis.pubsub()` a `channel_name(id)`, llama a `publish_status(id, "verifying", None, client=fake_redis)` y comprueba que `json.loads(msg["data"]) == {"status": "verifying", "error": None}`.
  - `test_publish_status_swallows_redis_errors`: con un cliente cuyo `publish` lanza `RedisConnectionError`, `publish_status` vuelve sin lanzar nada.
  - `test_set_status_publishes_after_commit`: con `db_session` y un `Submission` guardado, `await orchestrator._set_status(db_session, sub, "scoring")` (con `get_redis` parcheado para devolver `fake_redis`) deja un mensaje con `status == "scoring"` en el canal.
  - `test_mark_failed_publishes_failed`: lo mismo con `orchestrator._mark_failed(str(id), "x")`, parcheando `async_session_factory` con `db_session_factory`. El mensaje es `{"status": "failed", "error": "x"}`.
  - `test_enqueue_failure_publishes_failed`: reutiliza el patrón de `test_rejected_submission_is_not_stored_or_enqueued` en `test_submissions.py`, con un `enqueue` que lanza `RedisConnectionError`. Comprueba que se publicó `failed` con `service.ENQUEUE_FAILURE`.
- [ ] **Paso 2:** `cd apps/api && uv run pytest tests/submissions/test_events.py -q`. Fallan porque no existe `app.modules.submissions.events`.
- [ ] **Paso 3: implementar** `events.py` y llamar a `await publish_status(submission.id, new_status, submission.error)` **después** del `commit` en los tres sitios. `_fail_stuck_cases` (un `UPDATE` masivo) no publica: el socket tiene su propia vida máxima y el cliente su `STALE_AFTER_MS`. Explícalo en un comentario.
- [ ] **Paso 4:** ejecuta otra vez `uv run pytest tests/submissions/test_events.py -q` y después `uv run pytest -q`. Todo pasa, incluidas las 345 pruebas que ya había.
- [ ] **Paso 5:** commit `feat(api): publicar los cambios de estado del caso en Redis`.

### Tarea 2: ticket del WebSocket

**Archivos:**
- Crear: `apps/api/app/modules/submissions/ws_tickets.py`
- Modificar: `apps/api/app/modules/submissions/routers.py`, con la ruta nueva después de `get_submission`
- Modificar: `apps/api/app/core/config.py`, con `rate_limit_ws_ticket_per_minute: int = Field(default=30, alias="RATE_LIMIT_WS_TICKET_PER_MINUTE")`
- Modificar: `apps/api/app/modules/submissions/schemas.py`, con `WsTicketResponse(ticket: str, expires_in: int)`
- Prueba: `apps/api/tests/submissions/test_ws_ticket.py`

**Interfaces:**
- Consume `service.get_submission(db, submission_id=..., user_id=...)`, `check_rate_limit` y `RateLimitExceeded`.
- Produce `TICKET_TTL_SECONDS = 30`.
- Produce `async issue_ticket(client, *, user_id: uuid.UUID, submission_id: uuid.UUID) -> str`. Hace `secrets.token_urlsafe(32)` y `set(f"ws-ticket:{token}", f"{user_id}:{submission_id}", ex=30)`.
- Produce `async redeem_ticket(client, ticket: str) -> tuple[uuid.UUID, uuid.UUID] | None`. Hace `getdel`. Devuelve `None` si no existe, si el formato no es válido o si `len(ticket) > 100`.
- Produce la ruta `POST /submissions/{submission_id}/ws-ticket -> WsTicketResponse`, con `get_current_user`, `require_csrf` y `get_redis_dependency`. Devuelve 404 `"Caso no encontrado."` si el caso no es del usuario. Tiene un límite por usuario (`f"ws-ticket:user:{user.id}"`) que devuelve 429 con `Retry-After`.

- [ ] **Paso 1: pruebas que fallan** (usa el `_login_full_session` y el `fake_enqueue` de `test_submissions.py`):
  - `test_ws_ticket_requires_auth`: sin sesión, la respuesta es 401.
  - `test_ws_ticket_requires_csrf`: con sesión pero sin `X-CSRF-Token`, la respuesta es 403.
  - `test_ws_ticket_for_own_case`: con sesión y un caso creado, la respuesta es 200, `expires_in == 30` y `fake_redis._values[f"ws-ticket:{ticket}"] == f"{user_id}:{sub_id}"` con `_ttls[...] == 30`.
  - `test_ws_ticket_for_someone_elses_case_is_404`: con un caso creado por otro usuario, la respuesta es 404.
  - `test_redeem_ticket_is_single_use`: el primer `redeem_ticket` devuelve `(user_id, sub_id)` y el segundo, `None`.
  - `test_redeem_ticket_rejects_garbage`: `redeem_ticket(fake_redis, "x" * 200)` y un valor guardado sin `:` devuelven `None`.
  - `test_ws_ticket_is_rate_limited`: con `RATE_LIMIT_WS_TICKET_PER_MINUTE` a 2 (en `monkeypatch.setattr` sobre `settings`), la tercera petición da 429.
- [ ] **Paso 2:** `uv run pytest tests/submissions/test_ws_ticket.py -q`. Fallan.
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4:** ejecuta la prueba y después `uv run pytest -q`. Todo pasa.
- [ ] **Paso 5:** commit `feat(api): ticket de un solo uso para el WebSocket del caso`.

### Tarea 3: endpoint WebSocket

**Archivos:**
- Crear: `apps/api/app/modules/submissions/live.py`
- Modificar: `apps/api/app/main.py`, con `app.include_router(live_router)`
- Modificar: `apps/api/app/core/config.py`, con `ws_max_seconds: int = Field(default=960, alias="WS_MAX_SECONDS")`
- Modificar: `apps/api/app/core/middleware.py`, **solo** si sus middlewares no dejan pasar un `scope["type"] == "websocket"` sin tocarlo (las pruebas lo descubrirán)
- Prueba: `apps/api/tests/submissions/test_live.py`

**Interfaces:**
- Consume `redeem_ticket` (tarea 2), `channel_name` y `publish_status` (tarea 1), y `settings.cors_origins`.
- Produce `router = APIRouter(tags=["submissions"])` con `@router.websocket("/ws/submissions/{submission_id}")`, recibiendo `submission_id: uuid.UUID`, `ticket: str` (query), `db: get_db` y `redis_client: get_redis_dependency`.
- Orden de las comprobaciones, **antes de `accept()`**, cerrando con `await websocket.close(code=1008)`:
  1. `websocket.headers.get("origin")` está en `settings.cors_origins`. Esto cubre CSWSH.
  2. `redeem_ticket(...)` no devuelve `None`.
  3. El `submission_id` del ticket coincide con el de la ruta y `service.get_submission(db, submission_id=..., user_id=...)` lo encuentra.
- Después: `accept()`, luego `pubsub.subscribe(channel_name(id))` y **después** se envía el estado actual (`{"status": ..., "error": ...}`, releído de la base). Si ya es terminal (`done` o `failed`), se cierra con 1000. Si no, se reenvía cada mensaje del canal con `send_text`, hasta que llega un estado terminal (y se cierra con 1000), el cliente se desconecta o se cumple `ws_max_seconds` (y se cierra con 1000). Siempre en un `finally`: `unsubscribe` y `aclose`. La desconexión del cliente se detecta con una tarea que hace `websocket.receive()` a la vez que el bucle de `get_message(ignore_subscribe_messages=True, timeout=1.0)`.

- [ ] **Paso 1: pruebas que fallan.** Son pruebas síncronas con `starlette.testclient.TestClient`, porque httpx no tiene WebSocket. El fixture propio `live_client` del archivo:
  - crea un motor `sqlite+aiosqlite:///:memory:` con `StaticPool` y un `async_sessionmaker` sin conectar todavía;
  - sobrescribe `get_db` y `get_redis_dependency` (con un `FakeRedis` nuevo);
  - abre `with TestClient(app) as client:` y ejecuta `client.portal.call(create_all)`, para que **todo** lo asíncrono corra en el bucle del portal;
  - siembra datos por HTTP con el mismo `client`: registro, login, `POST /submissions` (con `enqueue` parcheado) y `POST …/ws-ticket` con la cabecera CSRF de la cookie;
  - publica con `client.portal.call(fake_redis.publish, channel, payload)`;
  - y ejecuta `monkeypatch.setattr(settings, "cors_origins", ["https://fakesnews.vercel.app"])`.

  Las pruebas:
  - `test_rejects_a_foreign_origin`: con `Origin: https://evil.example`, `websocket_connect` lanza `WebSocketDisconnect`.
  - `test_rejects_a_missing_origin`: sin cabecera `Origin`, lo mismo.
  - `test_rejects_an_invalid_ticket`: con `ticket=nope`, lo mismo.
  - `test_ticket_cannot_be_reused`: la primera conexión se acepta y se cierra, y la segunda con el mismo ticket se rechaza.
  - `test_rejects_a_ticket_for_another_case`: el ticket es del caso A y la ruta, del caso B (los dos del mismo usuario). Se rechaza.
  - `test_sends_current_status_first`: el primer `receive_json()` es `{"status": "queued", "error": None}`.
  - `test_forwards_published_status_and_closes_on_done`: después del estado inicial, publica `verifying` y después `done`, y recibe los dos en orden. A continuación el servidor cierra con 1000.
  - `test_subscribes_before_reading_the_status`: con `service.get_submission` parcheado para que publique `extracting` antes de devolver el resultado, el cliente recibe ese mensaje y no se pierde. Es el punto 3 de «Puntos que revisar».
  - `test_closes_after_ws_max_seconds`: con `ws_max_seconds = 1`, el servidor cierra sin que llegue un estado terminal.
- [ ] **Paso 2:** `uv run pytest tests/submissions/test_live.py -q`. Fallan.
- [ ] **Paso 3: implementar** `live.py`, con un comentario de cabecera que diga que cubre el requisito «WebSockets» y que explique el ticket, porque la cookie es de `vercel.app` y no llega a la API. Si una prueba falla por los middlewares, haz que ignoren los scopes que no sean `http`.
- [ ] **Paso 4:** ejecuta `test_live.py` y después `uv run pytest -q` y `uv run ruff check . && uv run ruff format --check .`. Todo pasa.
- [ ] **Paso 5:** commit `feat(api): WebSocket del progreso del caso con validación de Origin`.

### Tarea 4: CSP y configuración del origen del WebSocket

**Archivos:**
- Modificar: `apps/web/lib/csp.mjs`, con `buildCsp({ dev, apiUrl, wsUrl })`
- Modificar: `apps/web/lib/csp.test.mjs`
- Modificar: `apps/web/next.config.ts`, para pasar `wsUrl: process.env.NEXT_PUBLIC_WS_URL ?? ""`
- Modificar: `apps/web/lib/api.ts`, para exportar `export function apiUrl(path: string): string` (que devuelve `${API_BASE_URL}${path}`; `rawFetch` pasa a usarla) y `export const WS_BASE_URL: string | null` (`process.env.NEXT_PUBLIC_WS_URL || null`)
- Modificar: `apps/web/Dockerfile` (con `ARG` y `ENV NEXT_PUBLIC_WS_URL=ws://localhost:8000`), `docker-compose.yml` (con el arg `NEXT_PUBLIC_WS_URL: ${NEXT_PUBLIC_WS_URL:-ws://localhost:8000}`) y `apps/web/README.md`, para documentar la variable, que se lee al compilar

**Interfaces:**
- Produce `buildCsp({ dev: boolean, apiUrl: string, wsUrl?: string }) -> string`. Si `wsUrl` cumple `^wss?:\/\/`, se añade `new URL(wsUrl).origin` a `connect-src`. Cualquier otro valor se ignora.
- Produce `apiUrl(path)` y `WS_BASE_URL`, que usan las tareas 5 y 8.

- [ ] **Paso 1: pruebas que fallan** en `csp.test.mjs`:
  - `wss://ca-x.azurecontainerapps.io/` añade exactamente `wss://ca-x.azurecontainerapps.io` a `connect-src`;
  - `ws://localhost:8000` añade `ws://localhost:8000`;
  - `javascript:alert(1)` y `""` no añaden nada;
  - las pruebas de antes siguen sin cambios.
- [ ] **Paso 2:** `cd apps/web && pnpm vitest run lib/csp.test.mjs`. Las pruebas nuevas fallan. Si `vitest.config.ts` no incluye `.mjs`, ejecuta las pruebas de `.mjs` como lo hace CI (mira el script `test` de `package.json` y `web.yml`).
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4:** ejecuta las pruebas de la web y `pnpm lint && pnpm tsc --noEmit`. Pasan.
- [ ] **Paso 5:** commit `feat(web): CSP y configuración para el origen del WebSocket`.

### Tarea 5: módulo del socket del caso, con vuelta al sondeo

**Archivos:**
- Crear: `apps/web/lib/submission-socket.ts`
- Prueba: `apps/web/lib/submission-socket.test.ts`

**Interfaces:**
- Consume `apiFetch`, `csrfHeaders` y `WS_BASE_URL` (tarea 4), y `SubmissionStatus` y `TERMINAL_STATUSES` (de `lib/cases.ts`).
- Produce `export interface StatusEvent { status: SubmissionStatus; error: string | null }`.
- Produce `export function requestWsTicket(id: string): Promise<string>`, que hace `POST /submissions/${id}/ws-ticket` con `csrfHeaders()` y devuelve `.ticket`.
- Produce `export function socketUrl(base: string, id: string, ticket: string): string`, que devuelve `${base sin "/" final}/ws/submissions/${encodeURIComponent(id)}?ticket=${encodeURIComponent(ticket)}`.
- Produce `export function watchSubmission(id: string, handlers: { onStatus: (e: StatusEvent) => void; onFallback: () => void }, options?: { wsBase?: string | null; openTimeoutMs?: number; WebSocketImpl?: typeof WebSocket; getTicket?: (id: string) => Promise<string> }): () => void`. Por defecto `wsBase` es `WS_BASE_URL`, `openTimeoutMs` es **5000**, `WebSocketImpl` es `globalThis.WebSocket` y `getTicket` es `requestWsTicket`. Devuelve una función de limpieza que cierra el socket y evita cualquier llamada posterior. **`onFallback` se llama como mucho una vez**, y nunca después de la limpieza ni después de un estado terminal. Pasa al sondeo cuando: no hay `wsBase` (en una microtarea); falla `getTicket`; el socket no abre en `openTimeoutMs`; hay un `error` o un `close` antes de un estado terminal; o llega un mensaje que no se puede leer como `StatusEvent`.

- [ ] **Paso 1: pruebas que fallan**, con una clase `FakeSocket` (que guarda la URL y tiene los métodos `open()`, `message(data)` y `close(code)`) y temporizadores falsos (`vi.useFakeTimers`):
  - `falls back when there is no ws base`: con `wsBase: null`, `onFallback` se llama una vez y no se crea ningún socket.
  - `falls back when the ticket request fails`.
  - `connects with the ticket in the url`: la URL es `wss://api.test/ws/submissions/abc?ticket=t%2B1` para el ticket `t+1`.
  - `forwards status events`: con `open()` y `message('{"status":"verifying","error":null}')`, `onStatus` recibe ese objeto.
  - `falls back if the socket does not open in time`: sin `open()`, al avanzar 5000 ms se llama `onFallback` una vez y el socket queda cerrado. Es el punto 1 de «Puntos que revisar».
  - `falls back when the socket closes before a terminal status`: `open()`, `message(verifying)`, `close(1006)` y se llama `onFallback`. Es el punto 4.
  - `does not fall back after done`: `message(done)` y después `close(1000)`. `onFallback` no se llama.
  - `does not fall back after cleanup`: la limpieza y después `close(1006)`. No se llama.
  - `falls back on a malformed message`: con `message("not json")`.
- [ ] **Paso 2:** `pnpm vitest run lib/submission-socket.test.ts`. Fallan.
- [ ] **Paso 3: implementar**, con un comentario de cabecera que diga que cubre el requisito «WebSockets» en el cliente.
- [ ] **Paso 4:** las pruebas pasan y `pnpm lint && pnpm tsc --noEmit` también.
- [ ] **Paso 5:** commit `feat(web): socket del progreso del caso con vuelta al sondeo`.

### Tarea 6: usar el socket en `/reports/[id]`, publicar el PR A y comprobarlo en producción

**Archivos:**
- Modificar: `apps/web/app/reports/[id]/report-client.tsx`
- Modificar: `apps/web/app/reports/[id]/page.tsx`

**Interfaces:**
- Consume `watchSubmission` (tarea 5).
- Produce `ReportClient(props: { id: string; initialSubmission?: Submission | null; initialReport?: Report | null })`. **La firma cambia:** recibe `id` y ya no `params`. La usa la tarea 11.
- `page.tsx` pasa a ser `async`: hace `const { id } = await params` y devuelve `<ReportClient id={id} />`.

- [ ] **Paso 1: implementar.** El efecto actual pasa a ser la función `startPolling()`, que sigue tal cual como respaldo. Al montar: si `initialSubmission` es terminal, se trata como ahora (con `done`, se carga el informe si no hay `initialReport`). Si no, se llama a `watchSubmission(id, { onStatus, onFallback: startPolling })`. `onStatus` actualiza `submission` conservando el resto de campos (`setSubmission(prev => prev && { ...prev, ...event })`) y, con `done`, llama a `getReport`. Si todavía no hay `submission`, se pide primero con `getSubmission(id)` una vez, para tener los datos completos (`raw_input`, `created_at`). Se mantienen la redirección por 401, el mensaje del 404, `STALE_AFTER_MS` y la limpieza al desmontar.
- [ ] **Paso 2:** `pnpm lint && pnpm tsc --noEmit && pnpm build`, y el e2e `pnpm exec playwright test`. Si `e2e/mock-api.ts` no tiene WebSocket, sin `NEXT_PUBLIC_WS_URL` la página usa el sondeo y el e2e tiene que seguir pasando igual. Todo en verde.
- [ ] **Paso 3: prueba manual en local:** `docker compose up` con `NEXT_PUBLIC_WS_URL=ws://localhost:8000`. Envía un texto; en DevTools, en Red y luego WS, se ve `101 Switching Protocols` y los mensajes de cada fase, y la barra avanza. Detén la API a mitad del caso: la página sigue con el sondeo.
- [ ] **Paso 4:** commit `feat(web): el informe sigue el progreso por WebSocket`, push, abrir el **PR A** y fusionarlo cuando CI y Sonar estén en verde. `api-deploy.yml` despliega la API.
- [ ] **Paso 5: tarea del dueño.** Añadir en Vercel (producción y preview) `NEXT_PUBLIC_WS_URL=wss://ca-fakesnews-api.proudpebble-539cdba7.northcentralus.azurecontainerapps.io` y volver a desplegar la web. Hay que pedírselo explícitamente.
- [ ] **Paso 6: comprobar en producción.** Envía un caso en https://fakesnews.vercel.app: se ve el `101` contra la API y los mensajes de cada fase, y la consola no muestra errores de CSP. Comprueba también que un `Origin` ajeno se rechaza (`curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" -H "Origin: https://evil.example" "https://<api>/ws/submissions/<id>?ticket=x"` responde 403).

## PR B: métricas web

### Tarea 7: `POST /vitals`

**Archivos:**
- Crear: `apps/api/app/modules/vitals/__init__.py`, `routers.py` y `schemas.py`
- Modificar: `apps/api/app/main.py`, con `include_router`
- Modificar: `apps/api/app/core/config.py`, con `rate_limit_vitals_per_minute: int = Field(default=60, alias="RATE_LIMIT_VITALS_PER_MINUTE")`
- Prueba: `apps/api/tests/vitals/__init__.py` y `test_vitals.py`

**Interfaces:**
- Consume `client_ip(request)`, `check_rate_limit` y `get_redis_dependency`.
- Produce `VitalReport(BaseModel, extra="forbid")` con estos campos:
  - `name: Literal["CLS","FCP","INP","LCP","TTFB"]`;
  - `value: float` con `ge=0`, `le=600_000`;
  - `rating: Literal["good","needs-improvement","poor"]`;
  - `route: str` con `max_length=100` y `pattern=r"^/[A-Za-z0-9/_\[\]-]*$"`;
  - `navigation_type: str | None` con `max_length=32`;
  - `id: str` con `max_length=64`.
- Produce `POST /vitals`, que devuelve 204. Lee `await request.body()` y responde 413 si pasa de **2048 bytes**. Parsea con `VitalReport.model_validate_json` (422 si falla) para aceptar `text/plain`, que es lo que manda `sendBeacon` sin preflight. Aplica el límite `f"vitals:ip:{client_ip(request)}"` y responde 429. Registra `logger.info("web_vital", name=..., value=..., rating=..., route=..., navigation_type=...)`. No pide sesión ni CSRF: explica en un comentario por qué y cómo se compensa.

- [ ] **Paso 1: pruebas que fallan:**
  - `test_vital_is_logged`: con un cuerpo válido y `content-type: text/plain`, la respuesta es 204 y el log capturado (como en `tests/core/test_logging.py`) tiene `event == "web_vital"`, `name == "INP"` y `route == "/reports/[id]"`.
  - `test_vital_rejects_unknown_metric`: con `name: "FID"`, la respuesta es 422 y no se registra nada.
  - `test_vital_rejects_a_real_report_url`: con `route: "/reports/9f…?x=1"`, la respuesta es 422.
  - `test_vital_rejects_extra_fields`: con `email: "a@b.c"`, la respuesta es 422.
  - `test_vital_rejects_oversized_body`: con 3000 bytes, la respuesta es 413 y no se registra nada. Es el punto 5 de «Puntos que revisar».
  - `test_vitals_are_rate_limited`: con el límite a 2, la tercera petición da 429.
- [ ] **Paso 2:** `uv run pytest tests/vitals -q`. Fallan.
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4:** ejecuta `uv run pytest -q`, `ruff check` y `ruff format --check`. Pasan.
- [ ] **Paso 5:** commit `feat(api): POST /vitals registra las métricas web en el log`.

### Tarea 8: `WebVitals` en la web y consulta KQL

**Archivos:**
- Crear: `apps/web/lib/web-vitals.ts` y su prueba `apps/web/lib/web-vitals.test.ts`
- Crear: `apps/web/components/web-vitals.tsx`
- Modificar: `apps/web/app/layout.tsx`, con `<WebVitals />` dentro de `<body>`
- Modificar: `docs/AZURE.md`, en la sección «Observabilidad», con la consulta KQL

**Interfaces:**
- Consume `apiUrl` (tarea 4).
- Produce `routeTemplate(pathname: string): string`, que cambia cada segmento con forma de UUID por `[id]` y quita la query y el hash. Por ejemplo, `/reports/1b4e28ba-2fa1-11d2-883f-0016d3cca427` pasa a `/reports/[id]`.
- Produce `toVitalPayload(metric: { name: string; value: number; rating: string; id: string; navigationType?: string }, pathname: string): VitalPayload`, que devuelve `{ name, value, rating, id, navigation_type, route }`.
- Produce `sendVital(payload: VitalPayload): void`, que serializa con `JSON.stringify` en un `Blob` de tipo **`text/plain`**, usa `navigator.sendBeacon(apiUrl("/vitals"), blob)` y, si no está disponible o devuelve `false`, `fetch(apiUrl("/vitals"), { method: "POST", body, keepalive: true, credentials: "include" })`. Nunca lanza excepciones.
- Produce `components/web-vitals.tsx` (con `"use client"`): `export function WebVitals(): null` llama a `useReportWebVitals(report)`, donde `report` es una función **del módulo**, para que la referencia sea estable como pide la guía de Next, y envía `toVitalPayload(metric, location.pathname)` solo si `metric.name` está en la lista permitida.

- [ ] **Paso 1: pruebas que fallan** de `routeTemplate` (UUID, ruta sin id, query y hash), de `toVitalPayload` y de `sendVital`:
  - usa `sendBeacon` con un `Blob` de tipo `text/plain`;
  - usa `fetch` con `keepalive` cuando `sendBeacon` devuelve `false`;
  - no lanza nada si `fetch` falla.
- [ ] **Paso 2:** `pnpm vitest run lib/web-vitals.test.ts`. Fallan.
- [ ] **Paso 3: implementar** y montar `<WebVitals />` en el layout.
- [ ] **Paso 4:** `pnpm lint && pnpm tsc --noEmit && pnpm build`. Con Lighthouse móvil sobre `pnpm start`, la landing no baja respecto a `main` (con un margen de ±2, ver la memoria de Lighthouse).
- [ ] **Paso 5:** en `docs/AZURE.md#observabilidad`, añade esta consulta:
  ```kusto
  ContainerAppConsoleLogs_CL
  | where ContainerAppName_s == "ca-fakesnews-api" and Log_s has "web_vital"
  | extend e = parse_json(Log_s)
  | project TimeGenerated, name = tostring(e.name), value = todouble(e.value), rating = tostring(e.rating), route = tostring(e.route)
  | order by TimeGenerated desc
  ```
  Ajusta los nombres de las columnas a los que ya usa `alert-fakesnews-errors` (en `infra/modules/monitoring.bicep` o el módulo de alertas). Comprueba allí que la alerta filtra por nivel `error` y que un `info` de `web_vital` **no** la dispara. Si no fuera así, excluye `web_vital` de la consulta de la alerta en el Bicep.
- [ ] **Paso 6:** commit `feat(web): enviar INP, LCP y CLS a la API con useReportWebVitals`, abrir el **PR B** y fusionarlo con todo en verde. Después, en producción: navega por la web, haz clic en varios botones (para que haya INP), cambia de pestaña (para que se envíen las métricas) y comprueba con la consulta KQL que aparecen filas de `INP`, `LCP` y `CLS`.

## PR C: cierre de sesión entre pestañas

### Tarea 9: `BroadcastChannel` para el cierre de sesión

**Archivos:**
- Crear: `apps/web/lib/auth-channel.ts` y su prueba `apps/web/lib/auth-channel.test.ts`
- Crear: `apps/web/components/auth/logout-sync.tsx`
- Modificar: `apps/web/lib/auth.ts`, para que `logout()` llame a `announceLogout()` en un `finally`, así se avisa aunque falle la petición, porque la pestaña actual va a `/login` igualmente
- Modificar: `apps/web/app/layout.tsx`, con `<LogoutSync />`

**Interfaces:**
- Produce `AUTH_CHANNEL = "fakesnews-auth"`.
- Produce `announceLogout(): void`, que abre el canal, hace `postMessage({ type: "logout" })` y lo cierra.
- Produce `onLogoutElsewhere(callback: () => void): () => void`, que se suscribe, filtra `data?.type === "logout"` y devuelve la función para darse de baja.
- Las dos funciones no hacen nada si `typeof BroadcastChannel === "undefined"`.
- Produce `components/auth/logout-sync.tsx` (con `"use client"`): `export function LogoutSync(): null`. Usa `onLogoutElsewhere`. En una ruta privada (cualquiera que no sea `/`, `/login`, `/register` o `/sources`) hace `router.replace("/login")`. En una ruta pública hace `window.location.reload()`, para que la cabecera, que lee la cookie una sola vez, vuelva a mostrar «sin sesión».

- [ ] **Paso 1: pruebas que fallan:**
  - `announces logout to other listeners`: un listener creado con `onLogoutElsewhere` recibe la llamada cuando `announceLogout()` se ejecuta desde otra instancia. Usa el `BroadcastChannel` de Node, que reparte los mensajes entre instancias del mismo proceso, y espera con `vi.waitFor`.
  - `ignores other messages`: con `postMessage({ type: "x" })` no se llama.
  - `unsubscribe stops callbacks`.
  - `is a no-op without BroadcastChannel`: con `vi.stubGlobal("BroadcastChannel", undefined)`, ninguna de las dos funciones lanza nada.
- [ ] **Paso 2:** `pnpm vitest run lib/auth-channel.test.ts`. Fallan.
- [ ] **Paso 3: implementar**, con un comentario que diga que cubre el requisito «postMessage» con `BroadcastChannel.postMessage`.
- [ ] **Paso 4:** `pnpm lint && pnpm tsc --noEmit && pnpm build`, y el e2e. Pasan.
- [ ] **Paso 5:** commit `feat(web): cerrar la sesión en todas las pestañas con BroadcastChannel`, abrir el **PR C** y fusionarlo. Comprueba en producción con dos pestañas abiertas en `/history` que cerrar sesión en una lleva a la otra a `/login`.

## PR D: patrones de renderizado

### Tarea 10: `/sources` con ISR

**Archivos:**
- Crear: `apps/web/lib/server-api.ts` y su prueba `apps/web/lib/server-api.test.ts`
- Modificar: `apps/web/app/sources/page.tsx`
- Modificar: `apps/web/app/sources/sources-client.tsx`, para exportar `SourceSummary` y aceptar `initialSources`

**Interfaces:**
- Produce `serverApiBase(env = process.env): string`. Devuelve, por este orden: `API_PROXY_TARGET` sin `/` final; `NEXT_PUBLIC_API_URL` si es absoluta (`^https?://`); o `"http://localhost:8000"`. **No** usa `/api`, porque el servidor de Next no pasa por su propio proxy.
- Produce `class ServerApiError extends Error { status: number }`.
- Produce `serverFetch<T>(path: string, init?: RequestInit & { next?: { revalidate?: number } }): Promise<T>`, que lanza `ServerApiError` si la respuesta no es OK o falla la red.
- `sources/page.tsx` tiene `export const revalidate = 60` (con un comentario que diga que coincide con el `public, max-age=60` de `app/core/middleware.py:61`). Tiene `async function loadSources(): Promise<SourceSummary[] | null>`, que hace `serverFetch<{ sources: SourceSummary[] }>("/sources", { next: { revalidate: 60 } })` y ordena por `score` de mayor a menor. **Si falla:** durante `next build` (`process.env.NEXT_PHASE === PHASE_PRODUCTION_BUILD`, de `next/constants`) devuelve `null`; en una regeneración, **lanza la excepción**, para que Next siga sirviendo la última versión buena. La página renderiza `<SourcesClient initialSources={...} />`.
- `SourcesClient({ initialSources }: { initialSources: SourceSummary[] | null })`. Si `initialSources` no es `null`, el estado empieza con esa lista y **no** se llama a `apiFetch("/sources")`. Si es `null`, se hace como ahora. Lo que depende de la sesión (`hasSessionCookie` y `me()`) no cambia.

- [ ] **Paso 1: pruebas que fallan:** `serverApiBase` (los tres casos y la barra final) y `serverFetch` con MSW (lanza `ServerApiError` con `status: 503`, y devuelve el JSON cuando la respuesta es 200).
- [ ] **Paso 2:** `pnpm vitest run lib/server-api.test.ts`. Fallan.
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4:** con la API local en marcha, `pnpm build`. La salida del build marca `/sources` como ISR (prerenderizada con «Revalidate 1m»; usa el texto que imprima esta versión). Con la API apagada, el build sigue terminando bien. Después `pnpm start` y `curl -sI http://localhost:3000/sources`: el `cache-control` corresponde a ISR, no a `no-store`.
- [ ] **Paso 5:** commit `feat(web): /sources con ISR cada 60 s`.

### Tarea 11: `/reports/[id]` con SSR y streaming

**Archivos:**
- Modificar: `apps/web/app/reports/[id]/page.tsx`
- Crear: `apps/web/app/reports/[id]/report-loader.tsx` (un componente de servidor `async`)
- Modificar: `apps/web/lib/server-api.ts`, para añadir `loadInitialCase`, y su prueba

**Interfaces:**
- Consume `serverFetch` (tarea 10) y `ReportClient({ id, initialSubmission, initialReport })` (tarea 6).
- Produce `loadInitialCase(id: string, accessToken: string | undefined): Promise<{ submission: Submission; report: Report | null } | null>`:
  - sin token, devuelve `null`;
  - hace `serverFetch` de `/submissions/${id}` con `Cookie: access_token=…` (**solo** esa cookie) y `cache: "no-store"`;
  - si el estado es `done`, pide también `/reports/${id}`;
  - ante cualquier `ServerApiError` (401, 404, 5xx) o error de red devuelve `null`, y entonces el cliente hace lo de ahora.
- `page.tsx` devuelve `<Suspense fallback={<ReportFallback />}><ReportLoader params={params} /></Suspense>`. `ReportFallback` usa `AppShell` y `LoadingLine` (de `components/app-shell`), igual que el estado de carga actual.
- `ReportLoader` es `async`: hace `await params`, lee `(await cookies()).get("access_token")?.value`, llama a `loadInitialCase` y renderiza `<ReportClient id initialSubmission initialReport />`.

- [ ] **Paso 1: pruebas que fallan** de `loadInitialCase` con MSW:
  - sin token, devuelve `null` y no hace ninguna petición;
  - envía `cookie: access_token=abc` y ninguna otra;
  - con un caso `verifying`, devuelve `{ submission, report: null }`;
  - con `done`, también pide `/reports/{id}`;
  - con 401, 404 o un error de red, devuelve `null`.
- [ ] **Paso 2:** `pnpm vitest run lib/server-api.test.ts`. Las pruebas nuevas fallan.
- [ ] **Paso 3: implementar.**
- [ ] **Paso 4:** `pnpm lint && pnpm tsc --noEmit && pnpm build` (la ruta sale como dinámica, `ƒ`) y el e2e. Después, en local y con sesión, `curl -N -b "access_token=…" http://localhost:3000/reports/<id>`: llega primero el HTML del fallback y después el contenido en otro trozo del mismo documento.
- [ ] **Paso 5:** commit `feat(web): /reports/[id] con SSR y streaming`.

### Tarea 12: `docs/RENDERIZADO.md`, PR D y comprobación final

**Archivos:**
- Crear: `docs/RENDERIZADO.md`
- Modificar: `README.md`, con un enlace en la sección de documentación
- Modificar: `docs/ESTADO.md`, con el historial de PR y la sección de la entrega

- [ ] **Paso 1: escribir `docs/RENDERIZADO.md`** con el contenido que fija el spec en «2. Patrones de renderizado» y «Documento `docs/RENDERIZADO.md`»:
  - qué es cada patrón (CSR, SSR, SSG, ISR y streaming), cuándo usarlo y qué cuesta;
  - una tabla con la ruta, el patrón y el enlace `archivo:línea`. CSR: `/history`, `/submit` y `/settings`. SSG: `/`. ISR: `/sources`. SSR con streaming: `/reports/[id]`;
  - **cómo comprobarlo en vivo**: `x-vercel-cache` (`MISS`, después `HIT` y `STALE`) en `/sources` con `curl -sI`; el streaming con `curl -N`; la landing estática; y el WebSocket (`101` en DevTools, el flujo del ticket y por qué no se usa la cookie);
  - y una sección corta que enlace dónde está cada uno de los otros tres requisitos (WebSockets, INP y `BroadcastChannel`), con sus archivos y pruebas, para el agente que revise el código.
- [ ] **Paso 2:** commit `docs: patrones de renderizado del proyecto`, abrir el **PR D** y fusionarlo con todo en verde.
- [ ] **Paso 3: comprobación final en producción**, siguiendo la lista de «Pruebas y comprobación» del spec:
  - el WebSocket da `101` y llegan los mensajes;
  - `/sources` pasa de `MISS` a `HIT` en `x-vercel-cache`;
  - `/reports/[id]` llega por streaming;
  - la consulta KQL de `web_vital` devuelve filas de INP;
  - el cierre de sesión se propaga con dos pestañas;
  - y Lighthouse móvil en la landing no empeora.
  Anota el resultado en `docs/ESTADO.md` (en un PR de docs) y actualiza la memoria del proyecto.
