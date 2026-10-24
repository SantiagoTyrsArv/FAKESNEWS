# Lighthouse móvil a 90+ — diseño

Fecha: 2026-10-24. Rama sugerida: `perf/mobile-lighthouse` (desde `main`).

## Intención

El usuario pasó PageSpeed Insights a `https://fakesnews.vercel.app/` (análisis `75oa4rreim`). En escritorio todo está bien, pero en móvil el Rendimiento se queda en 87. Quiere llegar a **90 o más en Rendimiento móvil**. De paso se corrigen los avisos que bajan Accesibilidad y Recomendaciones.

### Punto de partida (PageSpeed, 2026-10-24)

| | Rendimiento | Accesibilidad | Recomendaciones | SEO |
|---|---|---|---|---|
| Móvil | **87** | 96 | 96 | 100 |
| Escritorio | 100 | 96 | 96 | 100 |

- Métricas en móvil: FCP 1,7 s · **LCP 3,5 s** · TBT 0 ms · CLS 0 · Speed Index 4,6 s.
- Desglose del LCP en móvil según PageSpeed: TTFB 0 ms · retraso de carga 250 ms · carga 120 ms · **retraso de render 2.010 ms**. El elemento LCP es la imagen del collage del hero (`components/landing/hero-media.tsx`).
- Métricas en escritorio: FCP 0,3 s · LCP 0,6 s · CLS 0,014.

### Lo que dice una traza real (DevTools: móvil 412 px, CPU 4x, Slow 4G)

- **El LCP real es de 1,75 s.** PageSpeed calcula el suyo con una simulación (Lantern) que alarga mucho todo lo que esté en la ruta crítica. Por eso hay que acortar esa ruta y no solo hacer más rápida la imagen.
- **La cadena crítica más larga son las fuentes**: HTML (659 ms) → `chunks/…css` (17,3 KiB, bloquea el render) → `newsreader-latin-wght-normal.woff2`, con 3.971 ms en total. `public-sans` llega en 3.287 ms. Las fuentes entran por `@fontsource-variable/*` en `app/layout.tsx:3-4`. El navegador solo las descubre cuando ya tiene el CSS, nadie las precarga, y además el CSS incluye `@font-face` de subconjuntos que la web no usa (latin-ext, cirílico, vietnamita…).

## Objetivos

1. **Rendimiento móvil ≥ 90 en PageSpeed**: la mediana de 3 ejecuciones sobre la URL desplegada.
2. **El escritorio no empeora**: Rendimiento sigue en 100 y el LCP en torno a 0,6 s.
3. **Accesibilidad y Recomendaciones llegan a 100** en ambos factores de forma. SEO se queda en 100.
4. Las auditorías concretas de PageSpeed dejan de salir o bajan de forma clara:
   - `render-blocking-insight`
   - `image-delivery-insight`
   - `legacy-javascript-insight`
   - `unused-javascript`
   - `color-contrast`
   - `errors-in-console`

## Fuera de alcance

- Las auditorías manuales de accesibilidad que PageSpeed lista en inglés (focus traps, tab order, landmarks…). No son fallos.
- Otras páginas que no sean `/`, salvo que reciban el mismo cambio de rebote (fuentes, `browserslist`, `/auth/me`).
- El backend, salvo que haga falta algo para no llamar a `/auth/me` sin sesión. No se espera que haga falta.

## No se acepta

- Llegar a 90 ocultando contenido a Lighthouse o tratándolo de forma distinta (por user agent, por ejemplo).
- Que el escritorio pierda movimiento o cambie de aspecto.
- Que suba el CLS por el cambio de fuentes. Tiene que seguir en 0 o casi.

## Cambios

### 1. Fuentes con `next/font/local`

- Se sustituyen los `import "@fontsource-variable/…"` de `app/layout.tsx` por `next/font/local`. Así se mantiene la regla de que el build no dependa de Google Fonts, que es el motivo del comentario actual del layout.
- Los archivos son los woff2 variables **latin** de los paquetes de Fontsource que ya están instalados. Pueden cargarse desde `node_modules` o copiarse a `app/fonts/`; eso lo decide el builder. Solo hace falta el estilo normal, porque ni `app/` ni `components/` usan cursiva.
- `next/font` aporta precarga, `font-display: swap` y una fuente de respaldo ajustada (`adjustFontFallback`) para no mover el layout. Hoy `globals.css:74-75` nombra las familias a mano (`"Public Sans Variable"`, `"Newsreader Variable"`) en `--font-ui` y `--font-quote`. Con `next/font` esas dos variables pasan a la variable CSS que genera cada fuente (opción `variable`, aplicada en `<html>`), y se conservan las pilas de respaldo.
- Antes de quitar subconjuntos, hay que comprobar que todo el texto de la interfaz (español, con tildes, ñ, ¿¡, comillas «») está dentro de latin.
- Si `next/font` ya no las necesita, se quitan las dependencias `@fontsource-variable/*` del `package.json`.

### 2. Menos JS al inicio en móvil

Se aceptó recortar el movimiento en móvil si hace falta para llegar a 90. El escritorio queda igual.

- Hoy `MotionProvider` (`components/motion/motion-provider.tsx`) importa Lenis y GSAP de forma estática en el layout raíz, y lo mismo hacen los hooks de la portada (`useLandingMotion`, `Marquee`…). En táctil, Lenis ni siquiera se usa (`lenisAllowed` exige `!touch`).
- **Primer paso:** cargar Lenis con import dinámico solo cuando se va a usar. Después, medir.
- **Si con eso y los demás cambios no se llega a 90:** cargar GSAP y sus plugins después de la primera pintura (import dinámico al hidratar o en `requestIdleCallback`). En móvil, quitar o simplificar los efectos de scroll más caros de la portada (parallax de los pasos, marquesina con `scrub`, `data-tilt`). Lo que no puede cambiar es que el contenido ya pintado nunca dependa de que GSAP llegue.
- El orden y la parada los decide la medición: se hace lo mínimo que lleve la mediana a 90 o más con algo de margen. Cada recorte de movimiento en móvil se anota en el PR.

### 3. `sizes` de las imágenes

- **Pasos** (`app/page.tsx:234`): hoy dice `100vw` por debajo de 640 px, pero en móvil la tarjeta mide unos 378 px dentro de un viewport de 412 px, así que el navegador descarga 750 px. Hay que ajustar `sizes` al ancho real (algo como `calc(100vw - 2rem)` en móvil) y comprobar qué variante de `srcset` se elige con DPR 1,75.
- **Hero** (`components/landing/hero-media.tsx:16`): en móvil se muestra a unos 419 × 236 y descarga 677 px. Hay que revisar `sizes` y el `object-cover` (el recorte a la derecha hace que se use menos imagen de la que se baja).
- Ya existe `public/media/hero-keyframe-960.webp`. El builder comprueba si se usa y lo quita si sobra.

### 4. Contraste

- El token `--insufficient` del modo claro (`oklch(0.58 0.12 80)`, en `app/globals.css:114`) da unos 4,2:1 sobre `--card`. Hay que oscurecerlo hasta ≥ 4,5:1 sobre `--card` y sobre `--background`, sin cambiar el matiz. Afecta a `components/verdict.tsx` y a `settings/security`. El modo oscuro no se toca si ya cumple.
- **Marquesina** (`components/landing/marquee.tsx`) y **tarjeta de ejemplo del hero** (la `figure.cutout` con `data-tilt`): Lighthouse las marca, pero `text-paper` sobre `bg-ink` tiene mucho contraste. Hay que reproducirlo con Lighthouse local o axe y ver la causa. Si es un falso positivo por la rotación o el transform, se elige el arreglo más pequeño que lo quite sin cambiar el aspecto. Si hay un texto que falla de verdad (un rótulo pequeño de la tarjeta, por ejemplo), se corrige su color.

### 5. Nada de `/auth/me` sin sesión

- Hoy, un visitante anónimo de la portada provoca `GET /auth/me` → 401, y `apiFetch` intenta renovar con `POST /auth/refresh` → 403. Son dos errores en consola y dos peticiones inútiles. Pasa en `app/page.tsx:69` y también en `components/mfa-nudge.tsx`.
- Arreglo: si no existe la cookie `csrf_token` (`readCsrfCookie()` en `lib/api.ts:14`), se trata al visitante como anónimo y no se llama a la API. Con cookie, el comportamiento es el de hoy, renovación incluida.
- Ya está comprobado que la cookie `csrf_token` dura lo mismo que el refresh token (`max_age = refresh_token_expire_days`, en `apps/api/app/modules/auth/routers.py:62-73`) y que el logout la borra (`:91`). Mientras haya sesión renovable, existe la cookie.
- El mejor sitio para el cambio es `me()` en `lib/auth.ts`, porque cubre a todos los que lo llaman. Lo decide el builder.

### 6. `browserslist` moderno

- Se fija un `browserslist` en `apps/web/package.json` (o en `.browserslistrc`) con navegadores que no necesiten esos polyfills: `Array.prototype.at`, `flat`, `flatMap`, `Object.fromEntries`, `Object.hasOwn`, `trimStart` y `trimEnd`.
- Antes hay que consultar en `node_modules/next/dist/docs/` cómo trata esta versión de Next el `browserslist` y los polyfills, porque `AGENTS.md` avisa de que cambia respecto a versiones anteriores.

## Verificación

- **Mientras se desarrolla:** Lighthouse local en móvil (`npx lighthouse` o el MCP de DevTools) sobre `pnpm build && pnpm start`, para comparar antes y después de cada cambio. La nota local no es la de PageSpeed y solo sirve como tendencia.
- **Puerta final:** PageSpeed móvil y escritorio sobre el despliegue de vista previa de Vercel del PR, 3 ejecuciones cada uno, y se anota la mediana en el PR. Si se acaba la cuota de la API pública, se usa la web de pagespeed.web.dev. Antes de fusionar, el usuario puede repetirlo él mismo.
- Siguen pasando `pnpm lint`, `pnpm lint:css`, `tsc`, `pnpm build` y `pnpm test:motion`, más CI y Sonar sin issues nuevos.
- Prueba visual en el navegador: portada en móvil y en escritorio, con fuentes iguales a las de antes, sin salto de layout al cargar las fuentes, con el movimiento de escritorio intacto y con «Evidencia insuficiente» legible.

## Decisiones del asistente (revisar)

- `next/font/local` en vez de `next/font/google`, para no depender de Google en el build, igual que hoy.
- El recorte de movimiento es escalonado y se para en cuanto la medición llega a 90 con margen. No se recorta de antemano.
- La señal de «hay sesión» es la cookie `csrf_token`, que dura lo mismo que el refresh.
- La puerta es la mediana de 3 ejecuciones de PageSpeed sobre la vista previa de Vercel, porque una sola ejecución varía varios puntos.
- Todo va en un único PR, con un commit por cambio, para poder medir cada uno.

## Lo que queda al builder

- Dónde viven los woff2 y los nombres exactos de las variables de fuente.
- Los valores exactos de `sizes` y del nuevo `--insufficient`.
- La técnica concreta de carga diferida de Lenis y GSAP, y qué efectos se recortan en móvil si hace falta.
- El arreglo de los avisos de contraste de la marquesina y la tarjeta, después de reproducirlos.
- La lista exacta de `browserslist`.
