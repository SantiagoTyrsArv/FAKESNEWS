# Calidad del CSS en `apps/web`

Guía corta de las herramientas que cuidan el CSS de la web y de la línea base de tamaño
registrada hoy. Todos los comandos se ejecutan desde `apps/web`.

## Stylelint

Revisa los archivos `.css` con la configuración `stylelint-config-standard` (ver
`apps/web/stylelint.config.mjs`): errores de sintaxis, propiedades o valores no válidos,
duplicados, selectores mal escritos y convenciones de formato y nombres.

- `pnpm lint:css` revisa todos los `.css` y falla si hay errores. También corre en la CI.
- `pnpm lint:css:fix` corrige automáticamente lo que se puede arreglar (formato, notaciones).
- **VS Code:** instala la extensión *Stylelint* (`stylelint.vscode-stylelint`). El repo ya trae
  los ajustes en `.vscode/`, así que los errores aparecen mientras se escribe.
- **Ajustar una regla:** si una regla no encaja en un caso concreto, desactívala solo ahí y
  explica por qué:

  ```css
  /* stylelint-disable-next-line selector-class-pattern -- clase generada por una librería */
  .animate__fadeIn { }
  ```

  Si la regla no sirve para todo el proyecto, se cambia en `stylelint.config.mjs`.

## Auditoría con Project Wallace

`pnpm css:audit` analiza el CSS que genera el build. Hay que haber ejecutado antes `pnpm build`.
No corre en la CI; es para auditorías puntuales (antes y después de añadir animaciones o una
librería, o al sospechar que el CSS crece demasiado).

Imprime dos bloques: **Todo el build** (todo el CSS emitido) y **Portada (/)** (el CSS que carga
la página `/`). Con `pnpm css:audit --json <archivo>` se escribe `{ build, home }` en un JSON
para comparar entre versiones.

Cómo leer cada métrica:

| Métrica | Qué indica |
| --- | --- |
| Tamaño (y gzip) | Bytes del CSS. El gzip es lo que viaja por la red. |
| Reglas / Selectores / Declaraciones | Volumen del CSS. Si crecen sin que crezca la interfaz, hay duplicación. |
| Especificidad máxima y media | Qué tan "pesados" son los selectores. Una media que sube dificulta sobrescribir estilos. |
| Complejidad máxima de selector | Selectores largos o anidados; los muy altos son frágiles. |
| `!important` | Cuántas veces se fuerza un valor. Conviene que se mantenga bajo. |
| Colores únicos | Si crece mucho, probablemente falten variables o tokens de color. |
| Tamaños de fuente únicos | Una escala tipográfica sana tiene pocos valores. |
| `z-index` únicos | Pocos valores indican capas ordenadas. |
| Duraciones y funciones de temporización únicas | Consistencia de las animaciones; importarán cuando se añadan más. |

## DevTools: Coverage

Sirve para ver cuánto del CSS cargado se usa de verdad.

1. Abre DevTools y pulsa `Ctrl+Shift+P`, escribe "Show Coverage" y abre el panel.
2. Pulsa el botón de grabar (o "Start instrumenting coverage and reload page").
3. Recorre las páginas principales: `/`, `/login`, `/submit`, `/reports/[id]` y `/sources`.
4. Detén la grabación y mira el porcentaje sin usar del archivo CSS (barra roja = sin usar).

Aviso: el CSS sin usar en una página puede usarse en otra. Como hoy todo va en un solo archivo,
un porcentaje alto sin usar en una sola página no es un problema; lo relevante es el resultado
tras recorrer todas las páginas, y los estados que exigen interacción (menús, modales, hover).

## DevTools: CSS Overview

Da una vista rápida del CSS de una página.

1. En DevTools, abre el menú de paneles (`Ctrl+Shift+P`) y elige "Show CSS Overview".
2. Pulsa "Capture overview" con la página que quieres revisar abierta.
3. Qué mirar: **colores** (variantes casi iguales que se podrían unificar), **fuentes** (familias
   y tamaños de más), **declaraciones sin usar**, **media queries** (puntos de corte que no
   coinciden) y los contrastes con problemas.

Es una foto de una sola página: repite la captura en las rutas importantes.

## PurgeCSS y Lightning CSS

No se añaden.

- **PurgeCSS:** Tailwind 4 ya genera solo las clases que encuentra en el código. PurgeCSS solo
  podría quitar CSS propio o de librerías, y es justo el que se activa desde JavaScript
  (`animate__*`, clases de GSAP): lo borraría y rompería las animaciones.
- **Lightning CSS:** ya está en el build a través de Tailwind 4 (minificación, prefijos y sintaxis
  moderna); no se añade otra capa.
- **Criterio de revisión:** se reevalúa si el CSS de la portada crece de forma notable respecto a
  la línea base (por ejemplo, tras añadir animaciones). En ese caso se haría con una safelist
  explícita para `animate__*` y las clases de GSAP.

Decide la cifra de la **portada**, porque es lo que descarga un visitante.

## Línea base 2026-10-23

Medida con `pnpm build` y `pnpm css:audit` sobre Next 16.4.2.

Hoy la app emite un único archivo CSS, así que **"Todo el build" y "Portada (/)" son idénticos**.
Si Next empieza a dividir el CSS por ruta, las dos cifras dejarán de coincidir: el total del build
seguirá sumando todo, mientras que la portada solo contará lo que carga `/`.

| Métrica | Todo el build | Portada (/) |
| --- | --- | --- |
| Tamaño | 63.204 B | 63.204 B |
| Tamaño gzip | 12.784 B | 12.784 B |
| Reglas | 568 | 568 |
| Selectores | 621 | 621 |
| Declaraciones | 895 | 895 |
| Especificidad máxima | (0, 3, 0) | (0, 3, 0) |
| Especificidad media | (0, 1,09, 0,18) | (0, 1,09, 0,18) |
| Complejidad máxima de selector | 52 | 52 |
| `!important` | 1 | 1 |
| Colores únicos | 13 | 13 |
| Tamaños de fuente únicos | 20 | 20 |
| `z-index` únicos | 2 | 2 |
| Duraciones de animación únicas | 3 | 3 |
| Funciones de temporización únicas | 3 | 3 |
