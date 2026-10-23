# Herramientas de calidad de CSS — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stylelint en editor y CI, un comando de auditoría con Project Wallace, una guía de DevTools y una línea base del tamaño del CSS para `apps/web`.

**Architecture:** Todo vive en `apps/web`: config de Stylelint y scripts en `package.json`, un script Node (`scripts/css-audit.mjs`) que separa la lógica pura (resumir CSS, localizar el CSS de la portada) de la E/S para poder probarla con `node:test`. La CI es un único workflow de GitHub Actions que ejecuta lint, lint de CSS y build.

**Tech Stack:** Stylelint 17 + stylelint-config-standard 40, @projectwallace/css-analyzer 9, Node 22/24 (`node:test`), GitHub Actions, pnpm 11, Next.js 16.4.2, Tailwind 4.

**Spec:** `docs/superpowers/specs/2026-10-23-css-tooling-design.md`

## Global Constraints

- Todo comando se ejecuta en `apps/web` salvo que se diga otra cosa; gestor `pnpm` (11.22.0, de `packageManager`).
- Dependencias nuevas solo como `devDependencies`, en versiones que cumplan la antigüedad mínima de un día de pnpm.
- No se añade PurgeCSS ni otra capa de Lightning CSS.
- Falsos positivos de Stylelint por sintaxis de Tailwind se arreglan en la config, no en el CSS; cada regla desactivada o ajustada lleva un comentario con el porqué.
- Autofix de Stylelint no puede cambiar el render: colores `oklch(...)` y valores numéricos quedan equivalentes.
- CI: Node 22, `ubuntu-latest`, `pnpm install --frozen-lockfile`, sin secretos, filtro de rutas `apps/web/**` y el propio workflow, check no obligatorio.
- `css:audit` no corre en CI.
- Textos de documentación en español.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Windows: los globs de los scripts de `package.json` deben ir entre comillas dobles escapadas (`\"**/*.css\"`); comillas simples rompen en cmd. Verificado en Task 1 Step 6.
2. `css:audit` sin build previo: debe salir con código 1 y un mensaje que diga ejecutar `pnpm build`, no un stack trace. Test en Task 2.
3. Autofix que reescribe notación de color (`color-function-notation`, `alpha-value-notation`, `hue-degree-notation`, `lightness-notation`) en `globals.css`: revisar el diff y comparar build antes/después. Task 1 Step 5.
4. Stylelint recorriendo `.next/` o `node_modules/`: ralentiza y produce miles de errores. `.stylelintignore` en Task 1, verificado por el tiempo y la salida de `lint:css`.
5. HTML de la portada con varias hojas o rutas con `basePath`/query (`?dpl=`): `findPageStylesheets` debe devolver todas y normalizar la ruta. Test en Task 2.

---

### Task 1: Stylelint en el proyecto y en el editor

**Files:**
- Create: `apps/web/stylelint.config.mjs`, `apps/web/.stylelintignore`, `.vscode/extensions.json`, `.vscode/settings.json`
- Modify: `apps/web/package.json` (scripts y devDependencies), `apps/web/pnpm-lock.yaml`, posiblemente `apps/web/app/globals.css`

**Interfaces:**
- Produces: scripts `lint:css` y `lint:css:fix` en `apps/web/package.json` (Task 3 ejecuta `pnpm lint:css`).

- [ ] **Step 1: Instalar** `pnpm add -D stylelint stylelint-config-standard`. Esperado: versiones 17.x y 40.x (o la anterior que cumpla la antigüedad mínima) en `devDependencies`.

- [ ] **Step 2: Añadir scripts** en `package.json`: `"lint:css": "stylelint \"**/*.css\""` y `"lint:css:fix": "stylelint \"**/*.css\" --fix"`. Crear `.stylelintignore` con `.next/`, `node_modules/`, `public/`.

- [ ] **Step 3: Escribir `stylelint.config.mjs`** (`export default { extends: ["stylelint-config-standard"], rules: {...} }`) permitiendo en `at-rule-no-unknown` (y en `at-rule-no-deprecated`/`import-notation`/otras que choquen) las at-rules `theme`, `custom-variant`, `apply`, `utility`, `variant`, `source`, `reference`, `plugin`, `config`. Comentario por cada ajuste.

- [ ] **Step 4: Ejecutar** `pnpm lint:css`. Clasificar cada error según "Reglas para dejar el lint en verde" de la spec (falso positivo → config; estilo con autofix seguro → fix; convención del proyecto → ajustar regla con comentario; problema real → corregir y anotarlo para el PR).

- [ ] **Step 5: Aplicar** `pnpm lint:css:fix` solo si quedan errores de estilo autofixables. Revisar `git diff app/globals.css`: ningún `oklch(...)` ni valor cambia de significado (Review Focus 3). Ejecutar `pnpm build`; esperado: build OK.

- [ ] **Step 6: Verificar en verde y en rojo.** `pnpm lint:css` → sale 0 sin errores. Crear `app/__lint-check.css` con `a { colr: red; }`, ejecutar `pnpm lint:css` → sale distinto de 0 y menciona `property-no-unknown`; borrar el archivo. `pnpm lint` sigue pasando.

- [ ] **Step 7: Editor.** `.vscode/extensions.json` recomienda `stylelint.vscode-stylelint`. `.vscode/settings.json`: `"stylelint.validate": ["css"]`, `"stylelint.workingDirectories": ["apps/web"]`, `"css.validate": false`.

- [ ] **Step 8: Commit** `chore(web): add Stylelint with the standard config` (incluye lockfile, config, ignore, `.vscode/` y cualquier cambio en `globals.css`).

### Task 2: Auditoría con Project Wallace (`pnpm css:audit`)

**Files:**
- Create: `apps/web/scripts/css-audit.mjs`, `apps/web/scripts/css-audit-lib.mjs`, `apps/web/scripts/css-audit-lib.test.mjs`
- Modify: `apps/web/package.json`, `apps/web/pnpm-lock.yaml`

**Interfaces:**
- Produces (en `css-audit-lib.mjs`):
  - `summarize(css: string): Summary` — usa `analyze` de `@projectwallace/css-analyzer`. `Summary = { bytes, gzipBytes, rules, selectors, declarations, specificity: { max: [a,b,c], mean: [a,b,c] }, maxSelectorComplexity, importants, unique: { colors, fontSizes, zIndexes, durations, timingFunctions } }` (los `unique.*` son conteos).
  - `findPageStylesheets(html: string): string[]` — rutas `/_next/static/...css` de los `<link rel="stylesheet">`, sin query string, en orden.
  - `formatSummary(title: string, s: Summary): string` — bloque de texto legible en español.
- Produces (CLI): `pnpm css:audit [--json <archivo>]` imprime dos bloques, "Todo el build" y "Portada (/)".

- [ ] **Step 1: Instalar** `pnpm add -D @projectwallace/css-analyzer`. Añadir scripts `"css:audit": "node scripts/css-audit.mjs"` y `"test:scripts": "node --test scripts/"`.

- [ ] **Step 2: Escribir tests que fallan** en `css-audit-lib.test.mjs` (`node:test` + `node:assert/strict`):
  - `summarize` sobre `a{color:red}b{color:#f00;z-index:2}.x .y{animation-duration:200ms!important}` → `rules === 3`, `declarations === 4`, `importants === 1`, `unique.zIndexes === 1`, `unique.durations === 1`, `bytes === Buffer.byteLength(input)`, `gzipBytes > 0`.
  - `findPageStylesheets` sobre HTML con dos `<link rel="stylesheet" href="/_next/static/chunks/a.css?dpl=x">` y `<link rel="stylesheet" href="/_next/static/chunks/b.css">` y un `<link rel="preload" href="/c.css">` → `["/_next/static/chunks/a.css", "/_next/static/chunks/b.css"]`.
  - `findPageStylesheets("<html></html>")` → `[]`.
  - `formatSummary("Portada (/)", s)` contiene `"Portada (/)"` y el número de reglas.

- [ ] **Step 3: Ejecutar** `pnpm test:scripts`. Esperado: FAIL (módulo sin exportaciones).

- [ ] **Step 4: Implementar** las tres funciones en `css-audit-lib.mjs` (gzip con `node:zlib` `gzipSync`; HTML con regex sobre `<link ...>`, sin dependencias nuevas).

- [ ] **Step 5: Ejecutar** `pnpm test:scripts`. Esperado: PASS.

- [ ] **Step 6: Escribir `css-audit.mjs`** (E/S): si no existe `.next/static`, imprimir `No hay build. Ejecuta "pnpm build" antes de "pnpm css:audit".` y `process.exit(1)`. Si no, leer todos los `.css` bajo `.next/static/` (bloque "Todo el build") y los que lista `findPageStylesheets` del HTML prerenderizado de la portada en `.next/server/app/index.html` (bloque "Portada (/)"; si el archivo no existe, avisarlo y omitir el bloque). Con `--json <archivo>` escribir `{ build, home }` con los `Summary` completos.

- [ ] **Step 7: Verificar.** Renombrar temporalmente `.next` (o probar en un clon limpio) → `pnpm css:audit` sale 1 con el mensaje exacto (Review Focus 2). Luego `pnpm build && pnpm css:audit` → imprime ambos bloques con números > 0. `pnpm lint` pasa sobre los scripts nuevos.

- [ ] **Step 8: Commit** `chore(web): add a Project Wallace CSS audit command`.

### Task 3: CI de `apps/web`

**Files:**
- Create: `.github/workflows/web.yml`

**Interfaces:**
- Consumes: scripts `lint`, `lint:css` (Task 1), `build`, `test:scripts` (Task 2).

- [ ] **Step 1: Escribir el workflow** `name: web`; `on.push.branches: [main]` y `on.pull_request`, ambos con `paths: ["apps/web/**", ".github/workflows/web.yml"]`. Job `check` en `ubuntu-latest` con `defaults.run.working-directory: apps/web`: `actions/checkout@v4`, `pnpm/action-setup@v4` con `package_json_file: apps/web/package.json`, `actions/setup-node@v4` con `node-version: 22`, `cache: pnpm`, `cache-dependency-path: apps/web/pnpm-lock.yaml`; pasos `pnpm install --frozen-lockfile`, `pnpm lint`, `pnpm lint:css`, `pnpm test:scripts`, `pnpm build`.

- [ ] **Step 2: Validar en local** la sintaxis (`npx --yes @action-validator/cli .github/workflows/web.yml` o equivalente; si no hay validador disponible, revisar YAML con `node -e` + un parser). Ejecutar la misma secuencia de comandos en local con `pnpm install --frozen-lockfile` primero. Esperado: todos pasan.

- [ ] **Step 3: Commit** `ci(web): lint, lint CSS and build on every PR`. La verificación real (el check en verde) ocurre al abrir el PR; si falla, se corrige en esta tarea.

### Task 4: Guía de uso y línea base

**Files:**
- Create: `docs/css-quality.md`

**Interfaces:**
- Consumes: `lint:css`, `lint:css:fix` (Task 1); `css:audit` y su salida (Task 2).

- [ ] **Step 1: Medir la línea base**: `pnpm build && pnpm css:audit --json <scratchpad>/baseline.json`. Anotar de ambos bloques: bytes, gzip, reglas, selectores, declaraciones, especificidad máx./media, `!important`, colores, tamaños de fuente, `z-index`, duraciones, easings.

- [ ] **Step 2: Escribir `docs/css-quality.md`** en español, con secciones: "Stylelint" (qué revisa, `lint:css`, `lint:css:fix`, extensión de VS Code, cómo ajustar una regla con comentario), "Auditoría con Project Wallace" (cuándo usar `css:audit`, cómo leer cada métrica), "DevTools: Coverage" (abrir con Ctrl+Shift+P → "Show Coverage", grabar recorriendo `/`, `/login`, `/submit`, `/reports/[id]`, `/sources`; aviso de que el CSS sin usar en una página puede usarse en otra), "DevTools: CSS Overview" (cómo capturarlo y qué mirar), "PurgeCSS y Lightning CSS" (por qué no se añade, resumen de la spec; criterio: se reevalúa si el CSS de la portada crece de forma notable, con safelist para `animate__*` y clases de GSAP), "Línea base 2026-10-23" (tabla con las cifras del Step 1, versión de Next 16.4.2).

- [ ] **Step 3: Verificar** que cada comando citado en el documento existe en `package.json` y que las cifras coinciden con `baseline.json`.

- [ ] **Step 4: Commit** `docs: add the CSS quality guide and size baseline`.
