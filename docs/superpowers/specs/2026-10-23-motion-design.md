# Animaciones en toda la web, con login y registro interactivos

Fecha: 2026-10-23 · Estado: borrador para aprobación

## Intención

La web ya tiene el lenguaje visual collage (spec `2026-10-23-collage-editorial-higgsfield-design.md`),
pero casi no se mueve. El dueño del producto quiere **más impacto visual**: que la gente se
sorprenda **al entrar, mientras hace scroll y al interactuar con el mouse**. La referencia de
intensidad es [Format, de Obys](https://format.obys.agency/): titulares que aparecen línea a línea,
scroll suave, cursor propio, parallax.

Pidió partir de Animate.css y aplicar principios generales de motion design; no es obligatorio usar
solo esa librería: se puede combinar con otras para acercarse a la referencia.

Además, el login y el registro deben ser un **"interactive login"** como el shot de Dribbble
[Characters Interactive Login Screen](https://dribbble.com/shots/27128944-Characters-Interactive-Login-Screen):
personajes geométricos con ojos que miran el cursor y reaccionan al formulario, en la **paleta collage**.

Las maquetas que el dueño revisó están en `.superpowers/brainstorm/593-1792794158/content/`
(`motion-portada.html` y `login-personajes.html`, git-ignorados). Son referencia de sensación, no
código a copiar.

## Objetivos

- **Portada (`/`) a intensidad completa.** Entrada coreografiada, animaciones ligadas al scroll e
  interacciones de mouse (detalle abajo).
- **Resto de páginas al 75% del impacto de la portada** (palabras del dueño): mismo vocabulario,
  recorridos más cortos y sin las piezas más llamativas.
- **Login y registro con personajes interactivos** en la paleta collage.
- Seguir principios de motion design: easing natural, duraciones cortas, escalonados, una sola cosa
  protagonista a la vez, movimiento con propósito.

## No objetivos

- Transiciones animadas entre páginas (cortina al navegar). *Decisión del agente*: chocan con el
  anti-objetivo de no hacer esperar; cada página anima su propia entrada.
- Cambiar textos, rutas, flujos o lógica de las páginas.
- Personajes en la verificación en dos pasos (`/login/2fa`): esa página va con el tratamiento
  general al 75% (decisión del dueño).
- Modo oscuro: no hay selector hoy; las animaciones no lo requieren.
- Rediseñar el layout de ninguna página.

## Anti-objetivos (palabras del dueño)

1. **Que vaya lento en el celular.**
2. **Que cueste leer información importante.**
3. **Tener que esperar (3 a 6 segundos) para poder hacer clic en algún lugar.**

Cómo se traducen (*decisiones del agente*):

- **Nunca bloquear la interacción.** Todo es clicable desde el primer frame, también mientras
  anima. Nada usa `pointer-events: none` sobre contenido ni overlays que tapen botones durante más
  de lo que dura la cortina. La entrada completa de la portada termina en **≤ 1,5 s**; la cortina
  dura ≤ 0,9 s, no intercepta clics y **solo aparece la primera visita a la portada en la sesión**
  (`sessionStorage`).
- **Celular fluido.** En dispositivos táctiles (`(hover: none)` o `(pointer: coarse)`): sin cursor
  propio, sin inclinación 3D, sin botones magnéticos y **sin Lenis** (scroll nativo). Solo se
  animan `transform` y `opacity` (y `clip-path` en los reveals de texto). Recorridos y escalonados
  más cortos en pantallas pequeñas. Ninguna librería de animación entra en el bundle de rutas que
  no la usan.
- **La información importante no se mueve.** En reportes (`/reports/[id]`), historial, fuentes,
  ajustes y formularios: el contenido entra una vez y queda quieto. Nada de parallax, marquesina,
  inclinación ni loops sobre citas, veredictos, tablas o campos. Los textos largos no se parten en
  líneas animadas; solo los títulos.
- **Movimiento reducido.** Con `prefers-reduced-motion: reduce`: todo aparece con un fundido de
  ≤ 200 ms o directamente visible, sin cortina, sin marquesina, sin parallax, sin Lenis, sin cursor
  propio, y los personajes quedan quietos con los ojos al frente (sin seguir al cursor ni
  parpadear). La CSS existente ya respeta esta preferencia; se mantiene.
- **Contenido visible sin JavaScript.** El estado inicial "oculto" de un elemento animado lo pone
  el JS al montar, no el CSS del servidor, para que el SSR muestre todo y un fallo de JS no deje la
  página en blanco. *El builder elige la técnica para evitar el parpadeo* (por ejemplo, una clase en
  `<html>` puesta por un script inline antes del primer pintado, que solo existe si hay JS y no hay
  reduced-motion).

## Restricciones

- `apps/web`: Next.js 16.4.2 (App Router; las páginas son client components), React 19.2,
  Tailwind 4, componentes shadcn/base-ui. Leer la guía de `node_modules/next/dist/docs/` antes de
  escribir código (lo pide `apps/web/AGENTS.md`).
- Se construye sobre los tokens de `app/globals.css` (`--paper`, `--collage-blue`,
  `--collage-orange`, `--ink`, colores de veredicto) y las clases `.cutout`, `.torn-top`, `.mark`,
  `.mark-draw`, `.kicker`. No se reemplazan.
- Ya existen `tw-animate-css` (lo usan los componentes shadcn) y dos keyframes propios
  (`hero-pan`, `mark-draw`). Se conservan.
- Calidad de CSS (PR #5): `pnpm lint:css` debe pasar; el CSS nuevo sigue la config de Stylelint.
  Después de construir, `pnpm css:audit` se compara con la línea base de `docs/css-quality.md`
  (portada: 63.204 B, 12.784 B gzip) y la nueva cifra se registra en ese documento.
- pnpm aplica antigüedad mínima de un día a las dependencias.
- Accesibilidad: contraste AA intacto, foco visible en todo momento (el cursor propio nunca
  oculta el foco de teclado), los personajes son decorativos (`aria-hidden`).

## Herramientas (decisión del agente, aceptada por el dueño como "puedes usar diferentes")

| Librería | Para qué |
|---|---|
| **Animate.css** 4.x | Entradas simples y puntuales (aparecer, deslizar) en páginas internas y elementos pequeños, aplicadas por clase. |
| **GSAP** 3.x con **ScrollTrigger** y **SplitText** | Línea de tiempo de la entrada, titulares línea a línea, animaciones ligadas al scroll, cursor, botones magnéticos, personajes. |
| **Lenis** | Scroll suave en escritorio (no en táctil ni con reduced-motion). |

Animate.css se usa donde basta una clase; GSAP donde hace falta coordinación, scroll o mouse. El
builder no debe duplicar la misma animación con las dos.

## Reglas de movimiento (decisión del agente)

- Easing por defecto `expo.out` / `cubic-bezier(0.16, 1, 0.3, 1)`; rebote suave (`back.out`) solo
  para "pegar" recortes y botones; `elastic.out` solo al soltar elementos magnéticos.
- Duraciones: 0,6–1,2 s para entradas; 0,2–0,45 s para respuestas a hover y foco.
- Escalonado 60–120 ms entre hermanos.
- Una sola cosa protagonista a la vez: lo secundario espera o se mueve menos.
- Los valores viven en un solo lugar (tokens/constantes compartidos), con el factor de intensidad
  1 (portada) y 0,75 (resto) aplicado sobre distancias, rotaciones y escalonados.

## Portada (`app/page.tsx`): intensidad 1

**Al entrar** (orden de la línea de tiempo):
1. Cortina de papel en tres franjas (naranja, azul, tinta) que se retira hacia arriba (solo la
   primera visita en la sesión).
2. Header (logo y navegación) baja y aparece.
3. Kicker, y el titular `h1` sube **línea a línea** desde una máscara, con una ligera rotación.
4. Párrafo y botones (los botones con un pequeño rebote).
5. El collage del hero (`HeroMedia`) aparece y la tarjeta del ejemplo **cae girada como un
   recorte que se pega** (rotación inicial ~-9°, termina en su `--cutout-rotate`).
6. Los subrayados de veredicto se dibujan (animación `mark-draw` existente, encadenada al final).

**Al hacer scroll:**
- Una **cinta tipo marquesina** "VERIFICA ✶ CONTRASTA ✶ CITA ✶" entre el hero y "Paso a paso",
  ligeramente girada, que avanza con el scroll (scrub). Texto decorativo: `aria-hidden`.
- Títulos de sección (`h2`) línea a línea al entrar en pantalla.
- Tarjetas de los pasos suben escalonadas; sus ilustraciones con **parallax** suave dentro del
  recorte.
- El resto de secciones de la portada (resultados posibles, `SourcesSection`) entran escalonadas.
- Lenis activo (escritorio).

**Con el mouse (solo escritorio):**
- **Cursor propio**: punto + anillo que sigue con retardo; sobre enlaces y botones el anillo crece,
  se rellena de `--collage-blue` y muestra "Ver". Se oculta al salir de la ventana. El cursor del
  sistema se mantiene en campos de texto.
- **Botones magnéticos** (CTA del hero y de secciones): siguen un poco al cursor y vuelven con
  rebote.
- **Recortes que se inclinan en 3D** hacia el cursor (tarjeta del ejemplo e ilustraciones de los
  pasos) y se enderezan.

## Páginas internas: intensidad 0,75

Aplica a `/history`, `/reports/[id]`, `/sources`, `/settings/security`, `/submit` (todas usan
`AppShell`) y a `/login/2fa`.

- Entrada: título (`PageHeading`) línea a línea y contenido escalonado al entrar en pantalla, en
  cada navegación. Recorridos y rotaciones al 75%.
- El header de `AppShell` anima su entrada **solo la primera vez en la sesión** (marca en
  `sessionStorage`, como la cortina); al navegar entre páginas internas ya está quieto
  (*decisión del agente*: `AppShell` se remonta en cada página y repetirlo cansa; no se mueve a un
  layout compartido para no cambiar la estructura de rutas).
- Cursor propio sin texto "Ver" (el anillo solo crece y cambia de borde), botones magnéticos más
  suaves, recortes que solo se enderezan y se elevan (sin 3D).
- Sin cortina, sin marquesina, sin parallax sobre contenido.
- Estados de carga (`LoadingLine`) y listas que llegan por red: el contenido nuevo entra una vez
  con un fundido corto; no se re-anima en cada actualización.
- Lenis activo en escritorio.

## Login y registro: personajes interactivos

En `components/auth-shell.tsx`, para `/login` y `/register`, el panel izquierdo cambia la
ilustración y la cita por un **escenario de papel** (`--paper` con grano) con **cuatro personajes**
recortados: uno alto azul, un semicírculo naranja con boca, un bloque tinta y uno de papel rayado
con borde tinta. Cada uno con dos ojos (blanco + pupila tinta). El wordmark se queda arriba.
*Decisión del agente*: la cita "Cada conclusión lleva su cita…" se conserva como texto pequeño en
el escenario, para no perder el mensaje de confianza.

Comportamiento (validado en la maqueta):

| Situación | Reacción |
|---|---|
| Carga | Entran desde abajo, escalonados. |
| Mouse en movimiento | Los ojos siguen el cursor; los cuerpos se inclinan un poco hacia él. Parpadeo aleatorio cada 2–6 s. |
| Foco y escritura en el correo | Se estiran (curiosos) y miran hacia el campo, siguiendo el avance del texto. |
| Foco en la contraseña (oculta) | Los dos de atrás se tapan los ojos con las manos; los demás miran hacia otro lado. |
| "Mostrar contraseña" | El de papel rayado se asoma a espiar; los otros siguen sin mirar. |
| Error de login / registro | Tiemblan brevemente, la boca del semicírculo se invierte ~1,4 s; el formulario hace un pequeño rebote horizontal. |
| Éxito | Ninguna celebración que retrase la navegación. |

- El formulario existente no cambia de lógica: los personajes escuchan foco, escritura, el botón
  de mostrar y el resultado (error/éxito) que la página ya conoce. Si el formulario actual no tiene
  "mostrar contraseña", se añade el botón (es la única UI nueva del formulario).
- **Celular** (*decisión del agente*): hoy el panel izquierdo está oculto en pantallas pequeñas. En
  móvil se muestra una **franja compacta** con los personajes sobre el formulario (altura ≤ 96 px,
  el wordmark va dentro de la franja para no sumar altura) que reacciona a foco, contraseña y error,
  pero no sigue ningún cursor. No debe empujar el botón de enviar fuera de la primera pantalla en un
  teléfono de 375×667. Se verifica en `/login` (también con el aviso `?registered=1`) y en
  `/register`; si en alguna de las dos no cabe, **en esa página la franja no se muestra en móvil**
  (el formulario manda).
- **Sin cursor propio, sin botones magnéticos y sin Lenis en `/login` y `/register`**
  (*decisión del agente*): los personajes son los protagonistas y ya siguen al cursor; un segundo
  elemento que lo sigue compite con ellos. Las páginas son cortas y no necesitan scroll suave.
- `/login/2fa` mantiene el panel actual con el tratamiento al 75%.
- Personajes en SVG o HTML/CSS (decisión del builder), animados con GSAP, `aria-hidden`.

## Rendimiento y verificación

- Lighthouse móvil de la portada, mediana de 3 ejecuciones antes (en `main`) y después
  (*decisión del agente*, margen tolerado): rendimiento ≥ el de `main` − 5 puntos, LCP como mucho
  +200 ms, CLS ≤ 0,1.
- **El `h1` del hero es candidato a LCP** (*decisión del agente*): en móvil (y con reduced-motion)
  no se oculta nunca; se pinta desde el SSR sin animación de entrada. En escritorio sí entra línea a
  línea, pero la máscara se aplica con `clip-path`/`transform` sobre texto ya pintado, sin
  `opacity: 0` ni `visibility: hidden` previos a la hidratación. La imagen del hero tampoco se
  oculta antes de cargar. Las animaciones no causan layout shift: el espacio de cada elemento existe
  desde el SSR.
- `pnpm lint`, `pnpm lint:css`, `pnpm test:scripts` y `pnpm build` pasan; la CI del PR en verde.
- `pnpm css:audit` antes/después; la cifra nueva de la portada queda registrada en
  `docs/css-quality.md`. Si crece mucho por Animate.css, importar solo lo que se use es preferible a
  PurgeCSS.
- Comprobación manual: en un celular (o emulación táctil) no hay cursor propio ni Lenis; con
  reduced-motion activado no hay cortina, marquesina ni seguimiento de cursor; todos los botones
  responden al primer clic durante la entrada.

## Lo que queda al builder

- Organización de componentes y hooks (por ejemplo, un proveedor de motion en el layout, hooks
  `useReveal`, componentes `Cursor`, `Marquee`, `AuthCharacters`).
- Versiones exactas dentro de la antigüedad mínima.
- Técnica anti-parpadeo con SSR.
- Formas exactas de los personajes, siempre en la paleta collage.
- Cómo cargar GSAP/Lenis solo en el cliente y solo donde se usan.
