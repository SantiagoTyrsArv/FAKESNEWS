# Patrones de renderizado (y el resto de la entrega de Programación Web)

Este documento explica qué patrón de renderizado usa cada ruta de la web (Next 16, App Router), por qué, y cómo comprobarlo en vivo en https://fakesnews.vercel.app. Al final enlaza dónde están los otros tres requisitos de la entrega: WebSockets, INP y `postMessage` con `BroadcastChannel`.

Cada pieza lleva en el código un comentario `Requirement: …` (por ejemplo `// Requirement: rendering patterns — ISR`), así que un `grep -rn "Requirement:" apps` las encuentra todas.

## Los patrones

| Patrón | Qué es | Cuándo conviene | Qué cuesta |
|---|---|---|---|
| **CSR** (Client-Side Rendering) | El servidor manda una estructura de la página (con estado de carga) y el navegador pide los datos con JavaScript después de hidratar. | Datos privados o muy interactivos, que cambian con cada acción del usuario y no interesan a buscadores. | El contenido aparece tarde (otra ida y vuelta después de cargar el JS) y sin JS no hay datos. |
| **SSG** (Static Site Generation) | La página se genera una vez, en `next build`, y se sirve como HTML estático desde la CDN. | Contenido igual para todos que solo cambia con un despliegue. | Para cambiar el contenido hay que volver a desplegar. |
| **ISR** (Incremental Static Regeneration) | Como SSG, pero la página caduca: pasado `revalidate`, la siguiente visita recibe la versión en caché y dispara una regeneración en segundo plano. | Datos públicos que cambian, pero no hace falta verlos al segundo. | Los datos pueden tener hasta `revalidate` segundos de antigüedad (y algo más si nadie visita la página). |
| **SSR** (Server-Side Rendering) | La página se genera en el servidor en cada petición, con los datos (y cookies) de esa petición. | Datos que dependen del usuario o tienen que estar al día en el primer pintado. | Cada visita cuesta trabajo de servidor y espera a la API; no se puede cachear en la CDN. |
| **Streaming** | SSR por partes: el servidor manda primero lo que ya tiene (cabecera, fallback de `<Suspense>`) y, en la misma respuesta HTTP, el resto cuando llegan los datos. | Con SSR cuando una parte depende de algo lento: el usuario ve la página enseguida en vez de una pantalla en blanco. | Hay que diseñar los límites de `<Suspense>` y su estado de carga; las cabeceras HTTP ya no se pueden cambiar una vez empieza el envío. |

## Qué usa cada ruta del proyecto

| Ruta | Patrón | Dónde |
|---|---|---|
| `/` (landing) | **SSG** | [`apps/web/app/page.tsx:63`](../apps/web/app/page.tsx). No pide datos: el build la prerenderiza (`○` en la salida de `next build`) y Vercel la sirve estática. Es un componente de cliente solo por las animaciones; el HTML ya viene completo. |
| `/sources` | **ISR** (60 s) | [`apps/web/app/sources/page.tsx:16`](../apps/web/app/sources/page.tsx) (`export const revalidate = 60`, igual que el `Cache-Control: public, max-age=60` de la API en [`apps/api/app/core/middleware.py:62`](../apps/api/app/core/middleware.py)). El componente de servidor pide `/sources` a la API con [`serverFetch`](../apps/web/lib/server-api.ts) y pasa la lista a `SourcesClient`, que conserva lo interactivo y lo que depende de la sesión (la cabecera). |
| `/reports/[id]` | **SSR con streaming** | [`apps/web/app/reports/[id]/page.tsx:16`](../apps/web/app/reports/[id]/page.tsx) (`<Suspense fallback>`) y [`report-loader.tsx:10`](../apps/web/app/reports/[id]/report-loader.tsx), un componente de servidor `async` que lee la cookie con `cookies()` y llama a [`loadInitialCase`](../apps/web/lib/server-api.ts). Después, en el navegador, el WebSocket sigue el caso en directo. |
| `/history`, `/submit`, `/settings/security`, `/login`, `/register` | **CSR** | Por ejemplo [`apps/web/app/history/history-client.tsx:89`](../apps/web/app/history/history-client.tsx): la página es una estructura estática y la lista de casos se pide en un `useEffect`. Son datos privados que cambian con cada acción, así que no tiene sentido cachearlos ni prerenderizarlos. |

### Qué pasa si algo falla

- **`/sources`:** si la API está apagada (escala a cero) **durante el build**, la página se publica sin datos y el cliente los pide como antes (CSR). Si falla **en una regeneración**, `loadSources` lanza el error y Next sigue sirviendo la última versión buena; lo reintenta en la siguiente visita.
- **`/reports/[id]`:** si el servidor no puede cargar el caso (el access token caducó y el servidor no puede renovarlo, el caso no existe o la API no responde), `loadInitialCase` devuelve `null` y `ReportClient` pide los datos en el navegador, donde sí se renueva la sesión. A la API se le manda **solo** la cookie `access_token`.

## Cómo comprobarlo en vivo

**SSG en la landing.** `curl -sI https://fakesnews.vercel.app/` devuelve `x-vercel-cache: HIT` (o `PRERENDER`): el HTML sale de la CDN sin pasar por una función.

**ISR en `/sources`.** Pide la cabecera varias veces:

```bash
curl -sI https://fakesnews.vercel.app/sources | grep -i -E "x-vercel-cache|cache-control|age"
```

La primera petición tras un despliegue puede dar `MISS` o `PRERENDER`; las siguientes, `HIT`. Pasados 60 s, una petición da `STALE` (sirve la copia vieja y regenera por detrás) y la siguiente vuelve a `HIT` con datos nuevos. En local, con `pnpm build && pnpm start`, la respuesta lleva `Cache-Control: s-maxage=60, stale-while-revalidate=…` y `x-nextjs-cache: HIT`.

**Streaming en `/reports/[id]`.** En el navegador: DevTools, Red, el documento de `/reports/<id>` y su pestaña de tiempos. El primer trozo trae la cabecera y «Cargando…»; el caso llega después en la misma respuesta. Con `curl` (la cookie la da la sesión del navegador):

```bash
curl -N -b "access_token=<token>" https://fakesnews.vercel.app/reports/<id>
```

Se ve llegar primero el HTML del fallback y, cuando responde la API, un `<div hidden id="S:0">` con el contenido y el script que lo coloca en su sitio.

**WebSocket.** En DevTools, Red, filtro **WS**: al abrir un caso que sigue en proceso aparece una conexión a `wss://<api>/ws/submissions/<id>?ticket=…` con `101 Switching Protocols`, y en **Mensajes** llega un `{"status": …, "error": null}` por cada fase. Se ve en la siguiente sección cómo se autentica.

## Dónde entra el WebSocket en el flujo

1. `/reports/[id]` llega por streaming con el estado actual del caso (SSR).
2. Si el caso sigue en proceso, el navegador pide un **ticket** con `POST /api/submissions/{id}/ws-ticket`. Pasa por el proxy `/api` de la web, así que viaja la cookie `httpOnly` de la sesión.
3. El navegador abre el WebSocket **directamente** contra la API (`NEXT_PUBLIC_WS_URL`), porque Vercel no hace de proxy de WebSockets. La cookie es del dominio de la web y no llegaría a la API: por eso se usa el ticket, que dura 30 s y solo sirve una vez.
4. La API valida el `Origin` (contra CSWSH), canjea el ticket y comprueba que el caso es del usuario. Se suscribe al canal de Redis `submission:{id}` **antes** de leer el estado, para no perder un cambio, y reenvía cada estado que publica el worker.
5. Si algo falla (la API tarda más de 5 s en abrir, se reinicia, no hay `NEXT_PUBLIC_WS_URL`), la página vuelve al sondeo de siempre.

## Los otros requisitos de la entrega

### WebSockets en lugar del sondeo

| Pieza | Archivo |
|---|---|
| Publicar cada cambio de estado en Redis | [`apps/api/app/modules/submissions/events.py:26`](../apps/api/app/modules/submissions/events.py) (`publish_status`) |
| Ticket de un solo uso (30 s, `GETDEL`) | [`ws_tickets.py:24`](../apps/api/app/modules/submissions/ws_tickets.py) y el endpoint en [`routers.py:108`](../apps/api/app/modules/submissions/routers.py) |
| Endpoint WebSocket | [`apps/api/app/modules/submissions/live.py:49`](../apps/api/app/modules/submissions/live.py) |
| Cliente con vuelta al sondeo | [`apps/web/lib/submission-socket.ts:57`](../apps/web/lib/submission-socket.ts) (`watchSubmission`), usado en [`report-client.tsx:96`](../apps/web/app/reports/[id]/report-client.tsx) |
| CSP que permite la conexión | [`apps/web/next.config.ts:14`](../apps/web/next.config.ts) |
| Pruebas | `apps/api/tests/submissions/test_live.py` (Origin, ticket reutilizado, suscribirse antes de leer…), `test_ws_ticket.py`, `apps/web/lib/submission-socket.test.ts` |

### INP (con LCP y CLS)

| Pieza | Archivo |
|---|---|
| `useReportWebVitals`, montado en el layout | [`apps/web/components/web-vitals.tsx`](../apps/web/components/web-vitals.tsx) y [`apps/web/app/layout.tsx:37`](../apps/web/app/layout.tsx) |
| Envío con `sendBeacon` y ruta sin ids | [`apps/web/lib/web-vitals.ts`](../apps/web/lib/web-vitals.ts) |
| `POST /vitals`, que lo escribe en el log | [`apps/api/app/modules/vitals/routers.py:51`](../apps/api/app/modules/vitals/routers.py) |
| Consultas KQL para verlo en Azure | [`docs/AZURE.md`](AZURE.md#consultas) (evento `web_vital`) |
| Pruebas | `apps/api/tests/vitals/test_vitals.py`, `apps/web/lib/web-vitals.test.ts` |

### `postMessage` con `BroadcastChannel` (cerrar sesión en todas las pestañas)

`BroadcastChannel.postMessage` es la API de `postMessage` entre contextos del mismo origen: al cerrar sesión en una pestaña, las demás reciben `{ type: "logout" }`.

| Pieza | Archivo |
|---|---|
| Canal `fakesnews-auth` | [`apps/web/lib/auth-channel.ts:17`](../apps/web/lib/auth-channel.ts) (`announceLogout`) y `:24` (`onLogoutElsewhere`) |
| `logout()` avisa siempre, aunque falle la petición | [`apps/web/lib/auth.ts`](../apps/web/lib/auth.ts) |
| Quien escucha, montado en el layout | [`apps/web/components/auth/logout-sync.tsx`](../apps/web/components/auth/logout-sync.tsx) y [`apps/web/app/layout.tsx:38`](../apps/web/app/layout.tsx) |
| Pruebas | `apps/web/lib/auth-channel.test.ts`, `apps/web/lib/auth.test.ts` |

Para verlo: dos pestañas con sesión en `/history`; al cerrar sesión en una, la otra va sola a `/login`. En una página pública (`/sources`) la otra pestaña se recarga y la cabecera pasa a «Iniciar sesión».
