# Medios generados con Higgsfield

Cada pieza de esta carpeta se generó una sola vez con la CLI `higgsfield` y se convirtió a WebP
con `sharp` (calidad 80). Para regenerar una pieza, usa el mismo modelo, los mismos ajustes y el
mismo prompt (estilo base + sujeto). El diseño está en
`docs/superpowers/specs/2026-10-23-collage-editorial-higgsfield-design.md`.

Workspace: plan gratuito, 10 créditos en total. GPT Image 2.5, el modelo previsto, exige el plan
Basic (`job_minimum_basic_plan_required`), así que las imágenes usan Seedream 5.0 Flash.

## Estilo base

Se antepone a todos los prompts de imagen:

> Editorial collage illustration in the style of a modern magazine op-ed spread mixed with mid-century newspaper print. Torn and cut paper pieces, newsprint scraps with abstract illegible grey text lines (no readable words, no letters), black halftone dot photo fragments of objects only, flat bold color blocks in deep cobalt blue (#2f4bff) and warm cut-paper orange (#ff6b3d) on an off-white paper background (#eceae4). Visible paper grain, slight drop shadows under pieces, slightly misaligned layers. No people, no faces, no hands, no photorealism, no logos, no readable text anywhere.

## Piezas

| Archivo | Modelo | Ajustes | Sujeto (va tras el estilo base, precedido de "Subject:") | Id de trabajo | Créditos |
|---|---|---|---|---|---|
| `hero-keyframe.webp` (+ `-960`) | `seedream_5_0_flash` | `resolution=2k`, `aspect_ratio=16:9`, seed 656152 | A smartphone chat bubble cut out of paper is being pulled apart into three separate paper strips floating apart, each strip a different shade; a large halftone magnifying glass over one strip; newsprint scraps around. Composition weighted to the right, calm empty paper area on the left third. | `601642f0-8556-4c32-897a-8fd04c960b75` | 0,5 |
| `step-1.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=4:3`, `image_references=<id del fotograma clave>`, seed 495512 | A cut-out chat message bubble being taped onto a sheet of paper with a strip of masking tape. Match the paper texture, palette and cut-paper style of the reference image. | `f2ed85b1-7041-484c-810b-33d063edc125` | 0,5 |
| `step-2.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=4:3`, `image_references=<id del fotograma clave>`, seed 734441 | A pair of black halftone scissors cutting a single long plain paper strip into three separate pieces; the strip carries only grey horizontal bars instead of text. Only paper shapes, the scissors and color blocks: no magazine pages, no photographs, no people, no headlines. Match the paper texture, palette and cut-paper style of the reference image. | `4dd20b68-2b34-44cd-b260-cab102b41247` | 0,5 |
| `step-3.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=4:3`, `image_references=<id del fotograma clave>`, seed 535296 | Three paper strips laid next to stacked newspaper clippings, a halftone magnifying glass comparing them. Match the paper texture, palette and cut-paper style of the reference image. | `514454a4-c898-4c2a-a922-ac78dab0f96e` | 0,5 |
| `step-4.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=4:3`, `image_references=<id del fotograma clave>`, seed 745011 | A neat paper dossier folder with three colored tabs and paper-clipped clippings. Only paper shapes: no magazine pages, no photographs of people, no headlines. Match the paper texture, palette and cut-paper style of the reference image. | `d56853a7-8dfc-4da1-ad29-e8fecab6f621` | 0,5 |
| `sources.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=4:3`, `image_references=<id del fotograma clave>`, seed 853081 | A tidy stack of folded newspapers and blank official-looking paper seals and stamps (no text on them), arranged like an archive. Only paper shapes: no magazine pages, no photographs of people, no headlines. Match the paper texture, palette and cut-paper style of the reference image. | `24946c11-6463-4a0e-b16b-ab603953f16a` | 0,5 |
| `auth.webp` | `seedream_5_0_flash` | `resolution=1.5k`, `aspect_ratio=3:4`, `image_references=<id del fotograma clave>`, seed 850067 | A tall arrangement of torn newsprint, a halftone magnifying glass and cobalt blocks, darker overall tone, empty dark area in the middle third for overlaid text. Only paper shapes: no magazine pages, no photographs of people, no headlines. Match the paper texture, palette and cut-paper style of the reference image. | `d0ce179f-9800-46d0-a2af-951664016344` | 0,5 |

Las piezas con `image_references` añaden al final del sujeto la frase *"Match the paper texture,
palette and cut-paper style of the reference image."*, que ya aparece en la tabla.

Descartes: un primer intento de `step-2` (`0dbccb36-62b8-4ebd-9b0f-1c297d5f8d7d`, 0,5 créditos)
salió con personas fotorrealistas y titulares falsos, y se repitió con el sujeto actual.

## Video descartado

Se probó un video del hero a partir del fotograma clave. Seedance 2.0 Mini y Grok Video 1.5 Lite
exigen el plan Basic. Seedance 1.5 Pro (`seedance1_5`, 4 s, 720p, sin audio, trabajo
`9ea398bb-ed40-49b5-8524-f1c43b301937`, 2,4 créditos) sí funcionó, pero se descartó: pesaba 5,3 MB,
añadía una lupa realista que rompía el estilo collage y no hacía bucle limpio. El hero usa el
fotograma clave fijo con un zoom y paneo lento en CSS (decisión del usuario).

Créditos gastados en total: 6,4 de 10.
