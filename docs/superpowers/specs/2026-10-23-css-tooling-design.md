# Herramientas de calidad de CSS para `apps/web`

Fecha: 2026-10-23 · Estado: borrador para aprobación

## Intención

El siguiente proyecto añade animaciones a toda la web (Animate.css, GSAP, Lenis), y eso va a
sumar bastante CSS. Antes de escribirlo queremos herramientas que vigilen la calidad del CSS de
forma continua y que permitan auditarlo cuando haga falta. Así el CSS nuevo nace revisado, en vez
de limpiarlo después.

El dueño del producto pidió cuatro herramientas, cada una con un uso concreto:

| Herramienta | Uso pedido |
|---|---|
| Stylelint + `stylelint-config-standard` | En el editor y en CI: calidad continua |
| Project Wallace | Auditorías puntuales de complejidad, especificidad y consistencia |
| DevTools (Coverage + CSS Overview) | Detectar CSS sin usar y tener una vista rápida |
| PurgeCSS o Lightning CSS en el build | Solo si el tamaño final importa |

## Objetivos

- `pnpm lint:css` en `apps/web` pasa sobre el CSS actual sin falsos positivos por la sintaxis de
  Tailwind 4.
- Los errores de Stylelint aparecen en el editor mientras se escribe.
- Un workflow de GitHub Actions ejecuta en cada PR y en cada push a `main`: `pnpm lint`,
  `pnpm lint:css` y `pnpm build`. Si falla uno, falla el check.
- `pnpm css:audit` genera, cuando se pide, el informe de Project Wallace sobre el CSS final del
  build (no sobre el código fuente: el CSS que llega al navegador es lo que importa).
- Un documento corto explica cuándo y cómo usar Coverage y CSS Overview de DevTools y cómo leer
  el informe de Wallace.
- Hay una línea base registrada: tamaño del CSS final y métricas principales de Wallace hoy, para
  comparar después de las animaciones. *Decisión del agente*: se registran dos cifras y se
  comparan siempre las mismas: (a) el total de todos los `.css` de `.next/static/` y (b) el CSS
  que carga la portada (`/`), tomado de los `<link rel="stylesheet">` del HTML que genera el
  build. La (b) es la que decide sobre PurgeCSS, porque es lo que descarga un visitante.

## No objetivos

- Corregir problemas de fondo del CSS que el audit encuentre. Este proyecto instala y mide; si
  Stylelint marca algo real en el CSS actual, se corrige solo lo necesario para dejar el lint en
  verde (ver "Reglas para dejar el lint en verde").
- Añadir PurgeCSS (ver "PurgeCSS y Lightning CSS").
- Lint de CSS en `apps/api` (no tiene CSS) ni tests de Python en la CI. La CI cubre solo
  `apps/web`. *Decisión del agente*: la API ya tiene su suite de pytest, pero meterla en la CI
  requiere Postgres y variables de entorno, y es otro trabajo.
- Automatizar Coverage con Playwright. Se ofreció como opción y queda fuera; si más adelante se
  quiere repetible, es una tarea aparte.

## Anti-objetivos

- **Que el lint bloquee el trabajo con ruido.** Si `stylelint-config-standard` choca con la
  sintaxis de Tailwind (`@theme`, `@custom-variant`, `@apply`, `@layer`, funciones como
  `--alpha()`), se ajusta la configuración, no el CSS. Una regla que da falsos positivos se
  desactiva con un comentario en la config explicando por qué.
- **Que la limpieza de CSS rompa las animaciones.** Ninguna herramienta del build puede borrar
  clases que se añaden desde JavaScript (`animate__*` de Animate.css, clases que alterna GSAP).
- Que la CI sea lenta o frágil: debe tardar pocos minutos y no depender de secretos.

## Restricciones

- `apps/web`: Next.js 16.4.2, Tailwind 4 con `@tailwindcss/postcss`, pnpm 11
  (`packageManager: pnpm@11.22.0`), Node 24 en local y Node 22 en producción
  (`apps/web/Dockerfile` usa `node:22-slim`).
- El CSS propio vive en un solo archivo, `app/globals.css` (≈320 líneas). Usa `@import`,
  `@custom-variant`, `@theme inline`, `@layer base/components`, `@apply` y `@keyframes`.
- pnpm aplica una antigüedad mínima de publicación de un día (`minimumReleaseAge`). Si la última
  versión de una herramienta es más nueva, se usa la anterior que cumpla.
- No hay CI en el repo hoy (no existe `.github/workflows`).
- La rama parte de `main` con el PR #4 (vulnerabilidades) ya fusionado: la línea base se mide
  sobre las versiones corregidas.

## Decisiones

### Stylelint

- Dependencias de desarrollo: `stylelint` y `stylelint-config-standard` (versiones actuales que
  cumplan la antigüedad mínima; hoy 17.x y 40.x).
- Config en `apps/web/stylelint.config.mjs`, extendiendo `stylelint-config-standard`.
- Compatibilidad con Tailwind 4: permitir las at-rules de Tailwind en `at-rule-no-unknown`
  (`theme`, `custom-variant`, `apply`, `utility`, `variant`, `source`, `reference`, `plugin`,
  `config`) y en cualquier otra regla que las rechace. *Decisión del agente*: preferir
  configurar `stylelint-config-standard` a mano antes que añadir un preset de Tailwind de
  terceros; si el builder encuentra uno mantenido y compatible con Tailwind 4 y Stylelint 17,
  puede usarlo y decirlo.
- Scripts en `package.json`: `lint:css` (`stylelint "**/*.css"`) y `lint:css:fix`. Ignorar
  `.next/`, `node_modules/` y `public/`.
- Editor: `.vscode/extensions.json` recomienda `stylelint.vscode-stylelint`, y
  `.vscode/settings.json` en la raíz del repo apunta la extensión a `apps/web`, valida `css`
  y desactiva la validación CSS nativa de VS Code (que no entiende Tailwind). *Decisión del
  agente*: se asume VS Code como editor.

### Reglas para dejar el lint en verde

Si Stylelint marca algo en el CSS actual:

1. Falso positivo por sintaxis de Tailwind → se arregla en la config.
2. Regla de estilo (orden, notación, nombres) con autofix seguro → `lint:css:fix`, y se revisa
   que el diff no cambie el render (por ejemplo, que no reescriba colores `oklch`).
3. Convención del proyecto que choca con la regla (por ejemplo, nombres de clase o keyframes) →
   se ajusta la regla en la config con un comentario.
4. Problema real (duplicados, selectores imposibles) → se corrige y se menciona en el PR.

### CI (GitHub Actions)

- `.github/workflows/web.yml`, en `push` a `main` y en `pull_request`, filtrado a cambios en
  `apps/web/**` y en el propio workflow.
- `ubuntu-latest`, Node 22 (la versión de producción; *decisión del agente*: el check debe
  garantizar que el build que se despliega funciona), pnpm vía `pnpm/action-setup` (versión tomada de `packageManager`),
  caché de pnpm con `actions/setup-node`, `pnpm install --frozen-lockfile`.
- Pasos en `apps/web`: `pnpm lint`, `pnpm lint:css`, `pnpm build`.
- El build no necesita secretos: todas las variables de entorno tienen valor por defecto o son
  opcionales (comprobado en la revisión).
- *Decisión del agente*: el check **no** se marca como obligatorio en la protección de rama de
  `main`. Con el filtro de rutas, un check obligatorio dejaría bloqueados los PRs que solo tocan
  `apps/api` o `docs/`. Si más adelante se quiere obligatorio, hay que quitar el filtro de rutas o
  añadir un job que pase siempre; configurar la protección es una acción manual en GitHub.

### Project Wallace

- Dependencia de desarrollo: `@projectwallace/css-analyzer` (o `wallace-cli` si su salida
  sirve mejor; decisión del builder).
- `pnpm css:audit`: requiere un build previo, concatena los `.css` de `.next/static/` y muestra
  un resumen legible: tamaño total, número de reglas, selectores, declaraciones, especificidad
  máxima y media, complejidad de selectores, `!important`, y valores únicos de colores, tamaños
  de fuente, `z-index`, duraciones y easings (estos dos últimos importarán con las animaciones).
  Con `--json` escribe el informe completo.
- No corre en la CI. Es para auditorías puntuales.

### DevTools

- Documento `apps/web/docs/css-quality.md` (o en `docs/` de la raíz, decisión del builder) con:
  - Coverage: cómo abrirlo, grabar una navegación por las páginas principales y leer el
    porcentaje sin usar, teniendo en cuenta que en una SPA el CSS "sin usar" en una página puede
    usarse en otra.
  - CSS Overview: cómo capturarlo y qué mirar (colores, fuentes, media queries, declaraciones
    sin usar).
  - Cómo usar `lint:css` y `css:audit`, y cuándo.

### PurgeCSS y Lightning CSS

- **No se añade PurgeCSS.** Tailwind 4 ya genera solo las clases que encuentra en el código y
  compila con Lightning CSS (minificación, prefijos y sintaxis moderna). PurgeCSS solo podría
  quitar CSS propio o de librerías, y es justo el que se activa desde JavaScript: borraría las
  animaciones.
- **Lightning CSS ya está en el build** a través de Tailwind 4; no se añade otra capa.
- La decisión se revisa con datos: el documento registra la línea base del tamaño del CSS final
  (sin comprimir y con gzip). Si después de las animaciones crece de forma notable, se evalúa
  entonces, con safelist explícita para `animate__*` y las clases de GSAP.

## Verificación

- `pnpm lint`, `pnpm lint:css` y `pnpm build` pasan en local.
- Un error introducido a propósito en un `.css` hace fallar `lint:css` (y se revierte).
- `pnpm css:audit` funciona tras `pnpm build` e imprime el resumen.
- El workflow pasa en el PR de esta rama.
- La línea base (tamaño del CSS y métricas de Wallace) queda escrita en el documento.

## Lo que queda al builder

- Versiones exactas de las dependencias, dentro de la antigüedad mínima.
- Nombres de reglas concretas a desactivar o ajustar, siempre con comentario.
- Implementación del script de `css:audit` (Node, sin dependencias extra más allá del analyzer)
  y su formato de salida.
- Ubicación del documento de uso.
