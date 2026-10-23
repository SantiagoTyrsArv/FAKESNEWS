# Rediseño collage editorial con Higgsfield: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar con Higgsfield 1 video y 6 imágenes en estilo collage editorial, integrarlos en la landing y el panel de acceso, y llevar una versión sobria del mismo lenguaje visual a las páginas internas.

**Architecture:** Los medios se generan una sola vez con la CLI `higgsfield`, se convierten localmente y se guardan como estáticos en `apps/web/public/media/`. El lenguaje visual vive en utilidades CSS nuevas de `app/globals.css` (tokens, tramas, filetes, recortes) que las páginas consumen por clase. El video del hero va en un componente cliente aislado que gestiona el póster, la carga diferida y `prefers-reduced-motion`.

**Tech Stack:** Next.js 16.3 (App Router, ver `apps/web/AGENTS.md`), React 19, Tailwind 4, shadcn/base-ui, CLI Higgsfield 1.2.2, `sharp` (solo en el scratchpad).

**Spec:** `docs/superpowers/specs/2026-10-23-collage-editorial-higgsfield-design.md`

## Global Constraints

- Tope duro: **10 créditos** de Higgsfield, sin comprar más. Antes de cada generación: `higgsfield workspace list` (saldo) y `higgsfield generate cost …` (coste). Si el coste supera el saldo, aplicar la escalera de recortes del spec, en orden, y no saltarse pasos.
- Imágenes: `gpt_image_2_5`, `--quality medium` (fotograma clave a `--resolution 2k`, el resto a `1k`). Video: `seedance_2_0_mini`, `--start_image` = fotograma clave, `--resolution 720p`, `--generate_audio false`.
- **Nada fotorrealista, nada de caras, nada de texto legible dentro de las imágenes.** Una pieza que lo incumpla se rechaza aunque cueste repetirla.
- Los colores de veredicto (`--supported`, `--contradicted`, `--insufficient` y sus `-tint`) no se usan como decoración.
- Sin cambios de copy en las páginas existentes salvo la sección nueva de fuentes y los `alt`. Español, sin "verdadero/falso".
- No añadir dependencias a `apps/web/package.json`. `sharp` se instala en el scratchpad.
- MP4 final ≤ 4 MB; si pesa más, parar y preguntar al usuario.
- Leer la guía relevante de `apps/web/node_modules/next/dist/docs/` antes de usar `next/image` o cualquier API de Next.
- Rama: `feat/collage-redesign`. Commits pequeños con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **`prefers-reduced-motion: reduce`**: el hero muestra solo el póster, sin `<video>` reproduciéndose, y los subrayados no se animan (ya existe). Se comprueba en la tarea 5.
2. **Video lento o que falla al cargar**: el póster sigue visible y la tarjeta superpuesta se lee; no hay hueco ni salto de layout. Se comprueba en la tarea 5 (red throttled y `src` roto).
3. **Móvil a 375 px**: los recortes rotados, el video y los bordes rasgados no provocan scroll horizontal. Se comprueba en las tareas 5, 6 y 7.
4. **Contraste sobre el collage**: la cita blanca del panel de acceso y la tarjeta del hero mantienen contraste AA sobre la ilustración (velo oscuro o recorte opaco detrás del texto). Se comprueba en las tareas 5 y 6.
5. **Sesión iniciada**: el hero sigue mostrando "Verificar un contenido" / "Ver mis casos" y la línea "Sesión iniciada como…", y la navegación no parpadea. Se comprueba en la tarea 5.

`apps/web` no tiene runner de tests. La verificación de cada tarea es `pnpm lint`, `pnpm build` y una revisión visual con el navegador (Claude in Chrome o Playwright) contra `pnpm dev`, con capturas a 1280 px y 375 px.

---

## Prompts (decisión fijada por el plan)

Estilo base, que se antepone a todos los prompts de imagen:

```
Editorial collage illustration in the style of a modern magazine op-ed spread mixed with mid-century newspaper print. Torn and cut paper pieces, newsprint scraps with abstract illegible grey text lines (no readable words, no letters), black halftone dot photo fragments of objects only, flat bold color blocks in deep cobalt blue (#2f4bff) and warm cut-paper orange (#ff6b3d) on an off-white paper background (#eceae4). Visible paper grain, slight drop shadows under pieces, slightly misaligned layers. No people, no faces, no hands, no photorealism, no logos, no readable text anywhere.
```

Sujetos:

| Archivo | Sujeto | Aspecto |
|---|---|---|
| `hero-keyframe` | A smartphone chat bubble cut out of paper is being pulled apart into three separate paper strips floating apart, each strip a different shade; a large halftone magnifying glass over one strip; newsprint scraps around. Composition weighted to the right, calm empty paper area on the left third. | 16:9 |
| `step-1` | A cut-out chat message bubble being taped onto a sheet of paper with a strip of masking tape. | 4:3 |
| `step-2` | Halftone scissors cutting a long paper strip of abstract text lines into three separate pieces. | 4:3 |
| `step-3` | Three paper strips laid next to stacked newspaper clippings, a halftone magnifying glass comparing them. | 4:3 |
| `step-4` | A neat paper dossier folder with three colored tabs and paper-clipped clippings. | 4:3 |
| `sources` | A tidy stack of folded newspapers and blank official-looking paper seals and stamps (no text on them), arranged like an archive. | 4:3 |
| `auth` | A tall arrangement of torn newsprint, a halftone magnifying glass and cobalt blocks, darker overall tone, empty dark area in the middle third for overlaid text. | 3:4 |

Prompt de video: `The paper strips drift slowly apart and settle, the magnifying glass glides gently across them, paper scraps flutter slightly. Stop-motion paper collage feel, subtle camera push-in, no new objects, no text, no people.`

---

### Task 1: Fundamentos visuales en CSS

**Files:**
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/components/app-shell.tsx` (`PageHeading`)
- Modify: `apps/web/components/site-header.tsx`
- Create: `apps/web/public/media/.gitkeep`

**Interfaces:**
- Produces (clases CSS en `@layer components`, usadas por las tareas 5-7):
  - Tokens: `--collage-blue`, `--collage-orange`, `--paper` (en `:root` y `.dark`), expuestos en `@theme inline` como `bg-collage-blue`, `bg-collage-orange`, `bg-paper`, `text-collage-blue`, etc.
  - `--font-heading: var(--font-quote)` en `@theme inline`, de modo que `font-heading` aplica Newsreader.
  - `.paper-texture`: grano de papel sutil como `background-image` (SVG `feTurbulence` en data URI, opacidad ≤ 0,05).
  - `.halftone`: trama de puntos (radial-gradient), color por `--halftone-color` (por defecto `currentColor`).
  - `.rule-double`: doble filete inferior (3px double `--foreground` al 70 %).
  - `.kicker`: versalitas, `letter-spacing: 0.14em`, 0,72rem, 600, `--collage-orange`.
  - `.cutout`: tarjeta recortada; sombra dura corta (`4px 4px 0` tinta al 15 %), rotación por `--cutout-rotate` (por defecto `-1deg`, máximo ±1,5deg), sin rotación con `prefers-reduced-motion: reduce`.
  - `.torn-top` / `.torn-bottom`: borde rasgado con `mask-image` SVG en data URI de 16px de alto.

- [ ] **Step 1:** Añadir tokens, `--font-heading` y las clases anteriores a `globals.css`. Aplicar `.paper-texture` al `body` en `@layer base`.
- [ ] **Step 2:** `PageHeading`: h1 con `font-heading` y peso 600 (Newsreader se ve pesado a 700+), sin otros cambios.
- [ ] **Step 3:** `SiteHeader`: sustituir `border-b` por `rule-double`.
- [ ] **Step 4:** Ejecutar `pnpm lint` y `pnpm build` en `apps/web`. Resultado esperado: ambos sin errores.
- [ ] **Step 5:** Revisión visual de `/sources` y `/login` a 1280 y 375 px: titulares en serif, textura apenas perceptible, doble filete en la cabecera y sin scroll horizontal.
- [ ] **Step 6:** Commit `feat(web): add editorial collage visual foundation`.

### Task 2: Fotograma clave del hero (punto de control con el usuario)

**Files:**
- Create: `apps/web/public/media/hero-keyframe.webp` (ancho 1920 y variante `hero-keyframe-960.webp`)
- Create: `apps/web/public/media/PROMPTS.md`
- Create (scratchpad, no se versiona): `convert.mjs`

**Interfaces:**
- Produces: el id de trabajo de Higgsfield del fotograma clave (anotado en `PROMPTS.md`), que usan las tareas 3 (`--image-references`) y 4 (`--start_image`).
- Produces: `node <scratchpad>/convert.mjs <input> <outputBase> <width...>`, que escribe `<outputBase>.webp` (primer ancho) y `<outputBase>-<w>.webp` para el resto, en WebP con calidad 80.

- [ ] **Step 1:** `higgsfield workspace list`; anotar el saldo (esperado: 10).
- [ ] **Step 2:** `higgsfield generate cost gpt_image_2_5 --prompt "<base + hero>" --quality medium --resolution 2k --aspect_ratio 16:9`. Esperado: 1 crédito.
- [ ] **Step 3:** `higgsfield generate create gpt_image_2_5 … --wait --json`; descargar el resultado al scratchpad.
- [ ] **Step 4:** Revisar la imagen contra los anti-objetivos (sin caras, sin texto legible, sin fotorrealismo, zona izquierda despejada). Si falla, aplicar la escalera de recortes antes de repetir.
- [ ] **Step 5:** `npm i sharp` en el scratchpad; escribir `convert.mjs`; convertir a 1920 y 960.
- [ ] **Step 6:** Crear `PROMPTS.md` con una tabla: archivo, modelo, ajustes, prompt completo, id de trabajo y créditos.
- [ ] **Step 7:** **Parar y enseñar la imagen al usuario.** No seguir sin su visto bueno.
- [ ] **Step 8:** Commit `feat(web): add Higgsfield hero keyframe`.

### Task 3: Las otras cinco ilustraciones

**Files:**
- Create: `apps/web/public/media/step-1.webp` … `step-4.webp`, `sources.webp` (ancho 800), `auth.webp` (ancho 1200)
- Modify: `apps/web/public/media/PROMPTS.md`

**Interfaces:**
- Consumes: el id de trabajo del fotograma clave (tarea 2) y `convert.mjs`.

- [ ] **Step 1:** Saldo y coste por pieza (esperado: 0,5 cada una, 2,5 en total).
- [ ] **Step 2:** Generar cada pieza con `--image-references <id del fotograma clave>` para heredar el estilo; revisar cada una contra los anti-objetivos antes de pasar a la siguiente.
- [ ] **Step 3:** Convertir con `convert.mjs` y anotar en `PROMPTS.md`.
- [ ] **Step 4:** Commit `feat(web): add Higgsfield step, sources and auth illustrations`.

### Task 4: Video del hero

**Files:**
- Create: `apps/web/public/media/hero.mp4`
- Modify: `apps/web/public/media/PROMPTS.md`

- [ ] **Step 1:** Saldo y `higgsfield generate cost seedance_2_0_mini --prompt "<video>" --start_image <id> --duration 5 --resolution 720p --generate_audio false`. Si no alcanza, probar `--duration 4` y después `--resolution 480p`; si tampoco alcanza, saltar al paso 5.
- [ ] **Step 2:** Generar con `--wait`, descargar y comprobar que el video arranca del fotograma clave y cumple los anti-objetivos.
- [ ] **Step 3:** Comprobar el tamaño; si supera 4 MB, parar y preguntar.
- [ ] **Step 4:** Anotar en `PROMPTS.md` y hacer commit `feat(web): add Higgsfield hero video`.
- [ ] **Step 5 (solo si no hay video):** anotar en `PROMPTS.md` que el hero usa el fotograma fijo con la animación CSS de la tarea 5, y hacer commit.

### Task 5: Landing

**Files:**
- Create: `apps/web/components/landing/hero-media.tsx`
- Create: `apps/web/components/landing/sources-section.tsx`
- Modify: `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: las clases de la tarea 1 y los medios de las tareas 2-4.
- Produces: `export function HeroMedia({ children }: { children: ReactNode })`, componente cliente que pinta el póster (`next/image`, `priority`, `sizes` según la columna) y, solo si `matchMedia("(prefers-reduced-motion: reduce)")` es falso y tras montar, un `<video src="/media/hero.mp4" poster muted loop playsInline autoPlay aria-hidden>` encima. `children` es la tarjeta superpuesta. Si no hay `hero.mp4` (tarea 4, paso 5), aplica en su lugar un keyframe CSS `ken-burns` de 20 s (escala 1→1,06), también desactivado con movimiento reducido.
- Produces: `export function SourcesSection()`, que no recibe props.

- [ ] **Step 1:** Hero: la columna derecha pasa a ser `<HeroMedia>` con la `<figure>` actual dentro, con `cutout` y `--cutout-rotate: -1.2deg`, desplazada hacia abajo e izquierda sobre el medio. El h1 usa `font-heading` y lleva encima un `<p className="kicker">Verificación de noticias</p>`. La columna izquierda no cambia de lógica ni de copy.
- [ ] **Step 2:** "Cómo se arma un reporte": añadir `step-N.webp` a cada paso (`next/image`, `alt=""` porque el título ya lo describe), con un marco `cutout` y rotaciones alternas de ±1deg. La sección lleva `torn-top` sobre `bg-card`.
- [ ] **Step 3:** `SourcesSection` entre los pasos y "Tres resultados": a la izquierda, kicker "Fuentes"; h2 "De dónde sale la confianza"; dos o tres frases basadas en el README (16 fuentes de confianza, historial de confiabilidad por fuente, sindicación contada como una sola voz) y un botón outline "Ver la confiabilidad de las fuentes" que enlaza a `/sources`. A la derecha, `sources.webp` con `alt` descriptivo. Fondo `bg-collage-blue` con texto blanco y `.halftone` decorativo con `--halftone-color` blanco al 10 %.
- [ ] **Step 4:** "Tres resultados" y el footer: solo h2 con `font-heading` y `rule-double` sobre el footer.
- [ ] **Step 5:** `pnpm lint` y `pnpm build` sin errores.
- [ ] **Step 6:** Revisión visual de los cinco puntos del Review Focus: reduced motion (emulado en DevTools), video roto (cambiar el `src` temporalmente), 375 px sin scroll horizontal, contraste de la tarjeta y sesión iniciada (usuario de `make seed`).
- [ ] **Step 7:** Commit `feat(web): rebuild the landing as an editorial collage`.

### Task 6: Panel de acceso

**Files:**
- Modify: `apps/web/components/auth-shell.tsx`

- [ ] **Step 1:** El `<aside>` pasa a usar `auth.webp` como fondo (`next/image fill`, `object-cover`, `alt=""`) con un velo `bg-ink/70` encima; la cita y el pie se mantienen por encima. El `Wordmark` blanco no cambia.
- [ ] **Step 2:** `pnpm build`; revisión visual de `/login`, `/register` y `/login/2fa` a 1280 px (contraste AA de la cita) y a 375 px (el panel sigue oculto).
- [ ] **Step 3:** Commit `feat(web): add collage illustration to the sign-in panel`.

### Task 7: Páginas internas sobrias y cierre

**Files:**
- Modify (solo si hace falta, tras revisarlas): `apps/web/app/history/page.tsx`, `apps/web/app/sources/page.tsx`, `apps/web/app/submit/page.tsx`, `apps/web/app/settings/security/page.tsx`, `apps/web/app/reports/[id]/page.tsx`

- [ ] **Step 1:** Revisar cada página a 1280 y 375 px con la base de la tarea 1. Donde haya estado vacío o cabecera de sección (h2), aplicar `font-heading`; en estados vacíos, como mucho un `.halftone` decorativo. **En `/reports/[id]` solo se tocan los titulares**, no las citas ni la evidencia.
- [ ] **Step 2:** `pnpm lint` y `pnpm build` sin errores.
- [ ] **Step 3:** Pasada final: landing, `/login`, `/history`, `/reports/<id de demo>` y `/sources` a 1280 y 375 px, con capturas.
- [ ] **Step 4:** `higgsfield workspace list`: anotar en `PROMPTS.md` los créditos gastados en total.
- [ ] **Step 5:** Commit `feat(web): carry the collage style to inner pages` y `git push -u origin feat/collage-redesign`.
