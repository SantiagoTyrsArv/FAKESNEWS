# Lighthouse móvil a 90+: plan de implementación

> **Para agentes:** sub-skill obligatoria: superpowers:executing-plans, ejecutado inline y sin subagentes (preferencia del usuario). Los pasos usan checkboxes (`- [ ]`).

**Objetivo:** que la portada de FakesNews saque **90 o más en Rendimiento móvil** de PageSpeed sin perder nada en escritorio, y que Accesibilidad y Recomendaciones lleguen a 100.

**Arquitectura:** acortar la ruta crítica de la portada. Las fuentes pasan a `next/font/local` con precarga, las imágenes descargan su tamaño real y Lenis se carga solo cuando se usa. Si la medición lo pide, GSAP se carga más tarde en móvil. Además se quitan el falso error de consola (`/auth/me` sin sesión) y los fallos de contraste.

**Tecnologías:** Next 16.4.2 (App Router), React 19.3, Tailwind 4, GSAP 3.15, Lenis 1.3, Lighthouse CLI.

**Especificación:** `docs/superpowers/specs/2026-10-24-mobile-lighthouse-design.md`

## Restricciones globales

- Todo se ejecuta desde `apps/web`. La rama es `perf/mobile-lighthouse` y ya existe, con la especificación commiteada.
- Lo que no cambia: Rendimiento de escritorio en 100 y LCP en torno a 0,6 s, CLS en 0 o casi, el aspecto y el movimiento de escritorio, y el modo oscuro.
- Prohibido tratar de forma distinta a Lighthouse (por user agent o similar).
- El build no puede depender de Google Fonts: se usa `next/font/local`.
- Antes de usar cualquier API de Next se lee su guía en `node_modules/next/dist/docs/` (`AGENTS.md`). Las de fuentes y navegadores ya están identificadas: `01-app/03-api-reference/02-components/font.md` y `03-architecture/supported-browsers.md`.
- Comprobaciones por tarea: `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`, `pnpm test:motion`, `pnpm test:lib` y `pnpm build`.
- Un commit por tarea, en inglés y con el estilo de `git log`, terminado en `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- `VULNERABILIDADES.md`, `AUDITORIA.md` y `SEGURIDAD.md` (raíz, sin seguimiento) no entran en ningún commit.

## Medición (la usan todas las tareas)

- **Local:** `pnpm build && pnpm start` (puerto 3000) y luego `npx -y lighthouse@12.6.0 http://localhost:3000/ --form-factor=mobile --screenEmulation.mobile --throttling-method=simulate --only-categories=performance,accessibility,best-practices,seo --output=json --output-path=<scratchpad>/lh-<tarea>-<n>.json --chrome-flags="--headless=new" --quiet`, 3 veces seguidas. Se anota la mediana de `categories.performance.score` y el LCP. Esta nota sirve para ver la tendencia; no es la de PageSpeed.
- **Final:** PageSpeed sobre la vista previa de Vercel del PR. Si la API no tiene cuota (`429`), se usa la web pagespeed.web.dev.

## Foco de revisión

1. **Usuario con sesión cuyo access token caducó** (tiene `csrf_token` y refresh, pero no access): `me()` tiene que seguir renovando y devolver su usuario, y la cabecera de la portada muestra su cuenta. Está cubierto en la Tarea 5, paso 4.
2. **Cambio de fuente al cargar:** con 4G lenta no debe haber salto visible del h1 ni del cuerpo, y el CLS sigue ≤ 0,02. Está cubierto en la Tarea 1, paso 5.
3. **Escritorio tras cargar Lenis de forma dinámica:** el scroll suave, ScrollTrigger (marquesina, reveals) y el cursor siguen funcionando, y no hay saltos al primer scroll. Si se navega antes de que Lenis termine de cargar, no queda una instancia huérfana. Está cubierto en la Tarea 3, paso 4.
4. **Modo oscuro y `prefers-reduced-motion`:** «Evidencia insuficiente» se sigue leyendo en oscuro (el token oscuro no cambia), y con movimiento reducido no se carga ni Lenis ni nada nuevo. Está cubierto en la Tarea 4, paso 4, y en la Tarea 3, paso 4.
5. **Otras páginas con imágenes y fuentes** (`/login`, `/register`, `/sources`): las fuentes se ven igual y no aparecen errores de consola nuevos. Está cubierto en la Tarea 8, paso 2.

---

### Tarea 0: Línea base

**Archivos:** ninguno.

- [ ] **Paso 1:** ejecutar la medición local 3 veces sobre `main` (la rama sin cambios de código). Anotar en el scratchpad la mediana de Rendimiento, el LCP, Accesibilidad y Recomendaciones. Todas las tareas siguientes se comparan con esta referencia.

### Tarea 1: Fuentes con `next/font/local`

**Archivos:**
- Crear: `app/fonts.ts`
- Modificar: `app/layout.tsx:1-4` y `<html>`; `app/globals.css:74-75`; `package.json` (dependencias)
- Crear: `app/fonts/newsreader-latin-wght-normal.woff2` y `app/fonts/public-sans-latin-wght-normal.woff2`, copiados de `node_modules/@fontsource-variable/*/files/`

**Interfaces:**
- Produce: `export const publicSans` y `export const newsreader` (resultado de `localFont`), con `variable: "--font-public-sans"` y `variable: "--font-newsreader"`. Ambos llevan `weight: "100 900"` para Public Sans y `"200 800"` para Newsreader (el rango lo dan los `@font-face` de Fontsource), `style: "normal"`, `display: "swap"` y `preload: true`.

- [ ] **Paso 1:** comprobar que todo el texto de la interfaz cabe en el subconjunto latin. Ejecutar `grep -rhoP "[^\x00-\x7F]" app components lib --include=*.tsx --include=*.ts | sort -u` y confirmar que cada carácter está en el `unicode-range` del `@font-face` latin de `node_modules/@fontsource-variable/newsreader/index.css`. Si alguno no está, parar e incluir también el woff2 de latin-ext.
- [ ] **Paso 2:** copiar los dos woff2 y crear `app/fonts.ts` con la interfaz de arriba (la sintaxis está en la guía `font.md`).
- [ ] **Paso 3:** en `layout.tsx`, quitar los dos imports de Fontsource y su comentario, y poner en su lugar un comentario que explique que se sirven en local para no depender de Google en el build. Añadir `${publicSans.variable} ${newsreader.variable}` al `className` de `<html>`. En `globals.css`, `--font-ui` pasa a `var(--font-public-sans), "Segoe UI", system-ui, sans-serif` y `--font-quote` a `var(--font-newsreader), georgia, "Times New Roman", serif`. Quitar `@fontsource-variable/*` de `package.json` y ejecutar `pnpm install`.
- [ ] **Paso 4:** pasar las comprobaciones globales. Además, `grep -c "@font-face" .next/static/**/*.css` (o el equivalente que haya en `.next`) tiene que dar solo 2 `@font-face` de nuestras familias, más los de respaldo que genera Next. El HTML de `/` lleva `<link rel="preload" as="font">` para los dos woff2.
- [ ] **Paso 5:** comprobarlo en el navegador (MCP de DevTools, 412 px, Slow 4G). El h1 se ve en Newsreader y el cuerpo en Public Sans, igual que antes (comparar capturas con `main`). La traza da CLS ≤ 0,02 y la cadena crítica ya no pasa por CSS → woff2.
- [ ] **Paso 6:** medición local (mediana de 3) y anotarla. Commit: `perf(web): self-host the fonts with next/font, latin only and preloaded`.

### Tarea 2: `sizes` de las imágenes de la portada

**Archivos:**
- Modificar: `app/page.tsx:234` y `components/landing/hero-media.tsx:16`

- [ ] **Paso 1:** con el MCP de DevTools, a 412 × 823 y DPR 1,75, medir el ancho que se ve de verdad (`getBoundingClientRect().width`) de una imagen de paso y del contenedor `[data-collage]`, y apuntar qué entrada de `srcset` carga hoy cada una (`currentSrc`).
- [ ] **Paso 2:** ajustar `sizes` para que por debajo de 640 px refleje ese ancho con un `calc(100vw - <padding total>)`, usando el padding real de la sección. Los tramos de escritorio no se tocan.
- [ ] **Paso 3:** comprobar `currentSrc` otra vez. Debe ser la variante más pequeña de `srcset` que sea ≥ ancho × 1,75. En escritorio (1440 px), `currentSrc` tiene que ser el mismo que antes.
- [ ] **Paso 4:** comprobar si `public/media/hero-keyframe-960.webp` se usa en algún sitio (`grep -rn "hero-keyframe-960" app components`). Si no se usa, borrarlo con `git rm`.
- [ ] **Paso 5:** comprobaciones globales y medición local. Commit: `perf(web): size the landing images to what mobile actually shows`.

### Tarea 3: Lenis bajo demanda

**Archivos:**
- Modificar: `components/motion/motion-provider.tsx:3,75-89`

- [ ] **Paso 1:** quitar `import Lenis from "lenis"`. Dentro del efecto de `lenisAllowed`, cargar con `import("lenis")` y crear la instancia solo si el efecto sigue vivo. Usar un flag `cancelled` en el cleanup, de modo que si el componente se desmonta o `lenisAllowed` cambia antes de que llegue el módulo, no se cree la instancia. Si llega a crearse, el cleanup la destruye igual que hoy y restaura `lagSmoothing`.
- [ ] **Paso 2:** comprobaciones globales. `pnpm build` tiene que sacar Lenis a un chunk propio que no aparezca en el HTML de `/` (comprobarlo buscando `lenis` en los `<script>` del HTML servido).
- [ ] **Paso 3:** medición local y anotarla.
- [ ] **Paso 4 (foco de revisión 3 y 4):** comprobarlo en el navegador.
  - **Escritorio:** el scroll suave funciona, la marquesina se mueve con el scroll, los reveals aparecen y el cursor sigue. Navegar de `/` a `/sources` y volver no lanza errores y deja una sola instancia de Lenis (`document.documentElement.classList.contains("lenis")` tras volver; no hay listeners duplicados).
  - **Móvil emulado y `prefers-reduced-motion: reduce`:** la petición del chunk de Lenis no aparece en la pestaña de red.
- [ ] **Paso 5:** commit: `perf(web): load Lenis only where smooth scroll runs`.

### Tarea 4: Contraste

**Archivos:**
- Modificar: `app/globals.css:114`
- Posibles: `components/landing/marquee.tsx` y el componente de la tarjeta de ejemplo del hero (localizarlo con `grep -rn "Mensaje reenviado" app components`)

- [ ] **Paso 1:** reproducir los avisos con `lighthouse_audit` del MCP de DevTools (móvil, modo navegación) sobre `localhost:3000`. Apuntar para cada nodo de `color-contrast` el par de colores y la relación que da axe.
- [ ] **Paso 2:** bajar la luminosidad de `--insufficient` en modo claro (L de `0.58` hacia abajo, con el mismo croma y matiz) hasta el primer valor que dé ≥ 4,5:1 sobre `--card` (`oklch(1 0 0)`) y sobre `--background` (`oklch(0.975 0.004 255)`). Hay que verificar el ratio calculándolo, no a ojo: con el `evaluate_script` del navegador, comparando los colores computados en `rgb()`. El bloque oscuro (`:160`) no se toca.
- [ ] **Paso 3:** marquesina y tarjeta. Si el paso 1 muestra un falso positivo (axe calcula mal el fondo por la rotación o los transforms), aplicar el arreglo más pequeño que lo quite sin cambiar lo que se ve. Por ejemplo, en la marquesina, que es `aria-hidden`, dar el color de fondo directamente al contenedor de texto. Si es un fallo real, oscurecer el color del texto afectado.
- [ ] **Paso 4 (foco de revisión 4):** volver a pasar `lighthouse_audit`. `color-contrast` tiene que pasar y Accesibilidad dar 100 en móvil y en escritorio. Comprobar a ojo «Evidencia insuficiente» en claro y en oscuro (con `emulate colorScheme`) en `/` y en `/settings/security` si hay manera de llegar.
- [ ] **Paso 5:** comprobaciones globales. Commit: `fix(web): reach AA contrast on the landing`.

### Tarea 5: Nada de `/auth/me` sin sesión

**Archivos:**
- Modificar: `lib/auth.ts:107-109`

**Interfaces:**
- Consume: `readCsrfCookie(): string | null` y `ApiError(message, status, body)` de `lib/api.ts`.
- Produce: `me()` mantiene su firma (`Promise<UserResponse>`). Si no hay cookie `csrf_token`, rechaza con `new ApiError("Not authenticated", 401, null)` sin hacer ninguna petición.

- [ ] **Paso 1:** implementar el guard en `me()`, con un comentario de una línea: la cookie CSRF vive lo mismo que el refresh, así que si no está no hay sesión que renovar.
- [ ] **Paso 2:** revisar los cuatro sitios que llaman a `me()` (`app/page.tsx:69`, `app/settings/security/page.tsx:30,60`, `app/sources/page.tsx:43`, `components/mfa-nudge.tsx:28`). Todos tienen que tratar el rechazo como «anónimo» o redirigir al login igual que con un 401 real. Si alguno distingue por `status`, el 401 sintético encaja.
- [ ] **Paso 3:** en el navegador y en una sesión limpia (`new_page` con `isolatedContext`): abrir `/` y comprobar que no hay peticiones a `/auth/me` ni a `/auth/refresh`, que la consola está sin errores y que la cabecera muestra «Entrar» o equivalente.
- [ ] **Paso 4 (foco de revisión 1):** con sesión. Iniciar sesión con una cuenta de prueba en local. Borrar solo la cookie `access_token` (desde DevTools, o esperar a que caduque) y recargar `/`: tiene que hacer `/auth/me` → 401 → `/auth/refresh` → 200 → `/auth/me` → 200, y la cabecera muestra la cuenta. Si no hay API local disponible, hacerlo en la vista previa de Vercel durante la Tarea 8.
- [ ] **Paso 5:** comprobaciones globales. Commit: `fix(web): skip /auth/me when there is no session cookie`.

### Tarea 6: JavaScript heredado

**Archivos:** depende de lo que se encuentre. Puede ser `package.json` (`browserslist`) o ninguno.

- [ ] **Paso 1:** Next 16 ya apunta por defecto a Chrome/Edge/Firefox 111 y Safari 16.4 (`supported-browsers.md`), y en `package.json` no hay `browserslist`. Por tanto, los polyfills que detecta PageSpeed (`Array.prototype.at`, `flat`, `flatMap`, `Object.fromEntries`, `Object.hasOwn`, `trimStart`, `trimEnd`) vienen de otro sitio. Localizar en `.next/static/chunks/` el chunk que los contiene (`grep -l "trimStart" .next/static/chunks/*.js`) y averiguar de qué módulo salen (con el source map si lo hay, o buscando el código alrededor).
- [ ] **Paso 2:** si salen de una dependencia nuestra, sustituirla o importar su build moderno. Si salen del propio runtime de Next o de React y no se pueden quitar desde la configuración documentada, no tocar nada y anotarlo en el PR como aviso aceptado: son 14 KiB y no cuentan para la nota.
- [ ] **Paso 3:** si hubo cambios, comprobaciones globales y commit: `perf(web): drop legacy polyfills from the client bundle`.

### Tarea 7: Recorte de movimiento en móvil (solo si hace falta)

**Archivos:** posibles `lib/motion/gsap.ts`, `components/landing/use-landing-motion.ts`, `components/landing/marquee.tsx` y `components/motion/*`.

- [ ] **Paso 1:** desplegar la rama en la vista previa (push y PR en borrador) y medir PageSpeed móvil 3 veces. **Si la mediana es ≥ 92, saltarse esta tarea** y anotarlo en el PR.
- [ ] **Paso 2:** si no llega, hacer la traza móvil local (CPU 4x, Slow 4G). Identificar qué JS se evalúa antes del LCP y cuánto pesa GSAP con ScrollTrigger y SplitText en el chunk inicial (`.next/` y la pestaña de red).
- [ ] **Paso 3:** en táctil (`touch` de `useMotion`), quitar los efectos de scroll de la portada que no se aprecian en móvil: el parallax de los pasos, el `scrub` de la marquesina y `data-tilt`. Que la marquesina quede quieta es aceptable. Si el chunk inicial sigue llevando GSAP, cargar `lib/motion/gsap.ts` con import dinámico desde los hooks que lo usan (8 archivos importan `@/lib/motion/gsap`), manteniendo las firmas de los hooks y el respaldo CSS de 5 s. En escritorio, el resultado tiene que ser idéntico.
- [ ] **Paso 4:** volver a medir. Repetir el paso 3 solo mientras la mediana siga por debajo de 90. Cada recorte se anota en el PR.
- [ ] **Paso 5:** comprobaciones globales, prueba de escritorio (foco de revisión 3) y commit: `perf(web): lighten landing motion on touch devices`.

### Tarea 8: Verificación final y PR

- [ ] **Paso 1:** PageSpeed sobre la vista previa: móvil × 3 y escritorio × 3, anotando las medianas de las cuatro categorías. Puerta: móvil Rendimiento ≥ 90, escritorio Rendimiento 100, Accesibilidad y Recomendaciones 100 en los dos, SEO 100.
- [ ] **Paso 2 (foco de revisión 5):** recorrer `/login`, `/register`, `/sources` y `/submit` en la vista previa (móvil y escritorio): las fuentes se ven bien y la consola está sin errores.
- [ ] **Paso 3:** el PR lleva una tabla con el antes y el después (los datos de la especificación y las medianas nuevas), la lista de recortes de movimiento si los hubo y la nota de la Tarea 6. Seguir `superpowers:finishing-a-development-branch`. Se fusiona tras CI verde y Sonar sin issues (ver memoria de autoridad para fusionar).
