# Rediseño "collage editorial" con piezas generadas en Higgsfield

Fecha: 2026-10-23 · Estado: borrador para aprobación

## Intención

La landing de FakesNews hoy es solo tipografía. Queremos que quien llega por primera vez
**confíe en la herramienta y entienda cómo funciona** (palabras del dueño del producto). Para eso:

1. Generar con Higgsfield **un video y seis imágenes fijas**, guardarlos en el repo y mostrarlos en
   la landing y en las pantallas de acceso. No hay generación en tiempo de ejecución: el visitante
   nunca llama a Higgsfield.
2. Darle a todo el frontend un lenguaje visual de **collage editorial**: una revista impresa de
   otra época, con recortes de periódico, fotos en semitono y bloques de color fuerte, pero con una
   maquetación moderna.

El collage se eligió frente a otras dos direcciones (grabado de periódico y risografía) en la
sesión de bocetos.

## Objetivos

- Que el hero explique el producto de un vistazo: un mensaje viral que se "desarma" en
  afirmaciones.
- Que cada paso de "Cómo se arma un reporte" tenga su ilustración.
- Que una sección nueva explique de dónde sale la confianza (las fuentes) y enlace a `/sources`.
- Que el resto de páginas compartan el lenguaje visual, en una versión más sobria.
- Gastar lo menos posible: el workspace de Higgsfield es el plan **gratuito, con 10 créditos**.

## No objetivos

- Generar contenido desde la app (ni para usuarios ni para administradores).
- Cambiar textos, flujos, rutas o lógica de las páginas internas.
- Añadir selector de modo oscuro (los tokens `.dark` existen pero no hay toggle; queda igual).
- Rediseñar la sección "Tres resultados posibles por afirmación": se queda como está.

## Anti-objetivos (fracaso aunque "funcione")

- **Nada fotorrealista.** Ni caras de personas inventadas ni escenas de "noticias" que parezcan
  reales. En una herramienta contra la desinformación, eso destruye la confianza. Las "fotos" del
  collage son recortes en semitono, claramente ilustrados.
- **Nada de texto legible generado por IA dentro de las imágenes.** Los modelos producen palabras
  deformadas o inventadas; un titular falso en un recorte sería exactamente lo que combatimos.
  Los recortes de periódico llevan líneas de texto ilegibles o abstractas, y todo texto real se
  pone en HTML.
- Que el reporte (`/reports/[id]`) pierda legibilidad: ahí la gente lee citas y evidencia.
- Que la landing se vuelva pesada o lenta: el video no debe bloquear la carga ni el LCP.

## Restricciones

- Next.js 16 + Tailwind 4 + componentes shadcn/base-ui ya existentes (`apps/web`). Se construye
  sobre los tokens de `app/globals.css`, las fuentes Public Sans y Newsreader y los colores de
  veredicto; no se reemplazan.
- Presupuesto Higgsfield: 10 créditos en total (ver tabla). Sin margen para iteraciones libres.
- Accesibilidad: respetar `prefers-reduced-motion`, contraste AA, imágenes decorativas con
  `alt=""`, video silencioso.
- El copy sigue en español y respeta el principio del producto: nunca "verdadero/falso".

## Modelos y presupuesto (decisión del agente, costes consultados con la CLI el 2026-10-23)

| Pieza | Modelo | Ajustes | Créditos |
|---|---|---|---|
| Fotograma clave del hero | GPT Image 2.5 (`gpt_image_2_5`) | `quality=medium`, `resolution=2k`, 16:9 | 1 |
| 4 ilustraciones de pasos | GPT Image 2.5 | `quality=medium`, `1k`, 4:3 | 4 × 0,5 = 2 |
| Ilustración de fuentes | GPT Image 2.5 | `quality=medium`, `1k`, 4:3 | 0,5 |
| Ilustración panel de acceso | GPT Image 2.5 | `quality=medium`, `1k`, 3:4 | 0,5 |
| Video del hero | Seedance 2.0 Mini (`seedance_2_0_mini`) | imagen→video desde el fotograma clave, 4–5 s, 720p, sin audio | 4–5 |
| **Total** | | | **8–9,5 de 10** |

Por qué estos modelos: GPT Image 2.5 en calidad media cuesta 0,5 créditos frente a 1,5 de Nano
Banana 2 y es el más fuerte del catálogo en diseño gráfico y composición. Seedance 2.0 Mini es el
video más barato que acepta fotograma inicial (`start_image`), así el video arranca exactamente
del collage aprobado y mantiene el estilo. Alternativa al mismo precio: Grok Video 1.5 Lite.

Orden de generación para no desperdiciar créditos: primero el fotograma clave, revisión del dueño,
después las demás imágenes usando el fotograma como `image_references` para mantener el estilo, y
el video al final.

**Tope duro de 10 créditos (decisión del dueño).** No se compran más créditos. Si una pieza sale
mal y no alcanza para repetirla, se recorta, en este orden: (1) la ilustración del panel de acceso
se sustituye por un recorte del fotograma clave; (2) las ilustraciones de pasos bajan a
`quality=low` (0,25); (3) el video baja a 4 s y 480p; (4) si aun así no alcanza, el hero usa el
fotograma clave fijo con una animación CSS ligera (paneo/zoom) en vez de video. Antes de cada
generación se consulta el saldo (`higgsfield workspace list`) y el coste
(`higgsfield generate cost`).

## Lenguaje visual

Paleta: se mantienen papel, tinta y el azul de evidencia (`--primary`). Se añaden dos tokens de
collage: un **azul de bloque** intenso (cercano a `--primary`, más saturado) y un **naranja
recorte** como acento cálido. El verde, rojo y ámbar quedan reservados a los veredictos y no se
usan como decoración, para que no pierdan significado.

Recursos gráficos (CSS/SVG, sin coste de Higgsfield):

- Titulares en serif (Newsreader) en lugar de sans en h1/h2.
- Bordes de papel rasgado entre secciones (máscara SVG).
- Tramas de semitono como fondo o sombra de bloques (patrón SVG en data URI).
- Filetes de revista: doble línea bajo cabeceras, "kicker" en versalitas sobre los titulares.
- Tarjetas que parecen recortes pegados: leve rotación (≤ 1,5°), sombra dura corta.

### Landing (`app/page.tsx`): intensidad completa

1. **Hero, opción B "capas".** A la izquierda, titular, texto y botones (sin cambios de copy). A
   la derecha, el video collage como fondo y, superpuesta encima como un recorte pegado, la
   tarjeta actual del mensaje marcado (con su animación de subrayado). Póster = fotograma clave,
   para que el LCP sea una imagen. Video `autoplay muted loop playsinline`, carga diferida tras el
   primer render; con `prefers-reduced-motion` se muestra solo el póster.
2. **"Cómo se arma un reporte"**: los 4 pasos con una ilustración cada uno.
   1. Pega el contenido: un mensaje de chat recortado y pegado en una hoja.
   2. Separamos las afirmaciones: tijeras separando tiras de texto.
   3. Las contrastamos con fuentes: tiras de texto junto a recortes de periódicos y una lupa.
   4. Recibes el reporte: un expediente ordenado con marcas de color.
3. **Sección nueva "De dónde sale la confianza"**: ilustración de periódicos apilados y sellos de
   organismos, con un texto breve sobre las 16 fuentes de confianza, el historial de confiabilidad
   y la deduplicación por sindicación, y un enlace a `/sources`. El copy final lo redacta el
   builder siguiendo el README y el tono de la landing.
4. "Tres resultados posibles": sin cambios de contenido; hereda solo tipografía y filetes.
5. Footer: hereda filetes.

### Acceso (`components/auth-shell.tsx`): login, registro y 2FA

El panel oscuro de la izquierda conserva su cita, pero gana la ilustración collage del panel de
acceso como fondo o recorte. En móvil el panel sigue oculto.

### Páginas internas: versión sobria

`/history`, `/submit`, `/reports/[id]`, `/sources`, `/settings/security`, vía `AppShell`,
`PageHeading` y `SiteHeader`:

- Titulares en serif y kicker en versalitas.
- Fondo con textura de papel muy sutil.
- Doble filete bajo la cabecera del sitio.
- Detalles de semitono solo en elementos vacíos o decorativos (estados vacíos, cabeceras).
- **Sin imágenes grandes, sin rotaciones ni bordes rasgados dentro del contenido.** En el reporte
  no se toca el cuerpo de citas y evidencia más allá de la tipografía de los titulares.

## Archivos y trazabilidad

- Medios en `apps/web/public/media/`: `hero-keyframe.webp`, `hero.mp4` (H.264, sin audio,
  optimizado para web), `step-1..4.webp`, `sources.webp`, `auth.webp`. Se descargan los
  originales de Higgsfield y se convierten y comprimen localmente.
- `apps/web/public/media/PROMPTS.md`: el prompt, el modelo, los ajustes y el id de trabajo de
  cada pieza, para poder regenerarla.
- `.superpowers/` (bocetos de esta sesión) se añade a `.gitignore`.
- Rama propia: `feat/collage-redesign`, creada desde `fix/phase-1-demo-hardening` *(decisión del
  agente: esa rama ya trae cambios en `/sources` y en la cabecera que este rediseño toca; partir de
  `main` provocaría conflictos)*.

## Lo que queda al builder

- Prompts exactos (respetando estilo, anti-objetivos y "sin texto legible").
- Valores concretos de los tokens nuevos, de las máscaras y de las tramas.
- Tamaños responsive de las imágenes. *(Decisión del agente: en esta máquina no hay ffmpeg,
  cwebp ni ImageMagick. Las imágenes se convierten a WebP con `sharp` desde el scratchpad, sin
  añadirlo a las dependencias del proyecto. El MP4 de Higgsfield se usa tal cual si pesa
  ≤ 4 MB; si pesa más, se para y se pregunta antes de instalar herramientas.)*
- Copy de la sección de fuentes y los textos `alt`.
- Verificación: `pnpm lint`, `pnpm build` y una revisión visual en el navegador de la landing,
  el login y una página interna, en móvil y escritorio.
