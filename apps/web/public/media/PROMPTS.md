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
