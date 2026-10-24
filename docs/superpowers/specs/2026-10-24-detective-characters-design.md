# Personajes detective — diseño

Fecha: 2026-10-24. Rama sugerida: `feat/detective-characters` (desde `main` una vez fusionado el PR #7).

## Intención

Los cuatro personajes de papel de `/login` y `/register` (`apps/web/components/auth/characters.tsx`) pasan a vestir de detective. Encaja con lo que hace FakesNews: investigar un mensaje y buscar las pruebas. La idea es del usuario. El objetivo es que la pantalla de acceso tenga más personalidad y un guiño al tema, sin perder lo que ya funciona.

## Qué cambia

### Vestuario: cada uno distinto, todos detectives (opción B del boceto)

| Personaje | Atuendo |
|---|---|
| Negro (`ink`), el jefe noir y el más elegante | Sombrero de fieltro con cinta roja, gabardina beige con solapas, corbata roja y cinturón. Es el único con lupa. |
| Azul (`blue`) | Gorra de cazador a cuadros (con viseras delante y detrás) y bufanda roja. |
| Rayado (`striped`) | Gorra de repartidor y un lápiz detrás de la oreja. |
| Naranja (`orange`) | Bombín negro y monóculo dorado con cordón. |

El boceto aprobado está en `.superpowers/brainstorm/1763-1792857983/content/detectives-estilo.html` (opción B). Es orientativo en proporciones y colores, y el trazo final puede ser más cuidado. Los colores salen de la paleta del collage que ya existe (`--ink`, `--collage-blue`, `--collage-orange`, papel). Los tonos nuevos, como el beige de la gabardina, el marrón de los cuadros, el rojo de corbata y bufanda o el dorado del monóculo y la lupa, se definen como variables junto a las de `.crew` en `globals.css`.

### La lupa del negro

- **Mientras mueves el ratón** (foco en ningún campo, solo escritorio): sostiene la lupa delante de un ojo y la orienta hacia el cursor. A través del cristal su ojo se ve más grande. El movimiento sigue la misma lógica de mirada que ya existe (`lookAt`, `pupilOffset`).
- **Al escribir en el correo o la contraseña:** se guarda la lupa en la gabardina. Al salir del campo (foco `none`) la vuelve a sacar.
- **Sin cursor** (móvil, o antes de mover el ratón): la lupa queda quieta en su mano, delante del ojo y apuntando al frente.

### El error: se quiebra el monóculo

En cada error nuevo (`errorKey` sube), al monóculo del naranja le aparece una grieta. Asoma una mano del naranja, se quita el monóculo roto, saca uno nuevo y se lo pone. El conjunto dura unos 1,5 s, en paralelo con el temblor y la boca hacia abajo, que se mantienen como hoy. Si llega otro error mientras tanto, la secuencia se reinicia desde el principio, igual que hace hoy `failure.restart()`. La lupa no participa en el error.

## Lo que no cambia

- Las formas, tamaños y posiciones de los cuatro cuerpos y la escena de 460×380 en unidades `--crew-u`.
- Todos los comportamientos actuales: entrada desde abajo, parpadeo, seguir el cursor, estirarse hacia el correo, taparse los ojos (azul y negro) con la contraseña, el rayado que espía cuando se muestra la contraseña, el temblor y la boca hacia abajo en el error, y el pequeño rebote del formulario.
- La franja compacta de móvil, que sigue sin aparecer en `/register` en móvil, y el escenario de escritorio.
- Que los personajes sean decorativos (`aria-hidden`) y que el marcado del servidor sea una pose fija igual a la del cliente.

## Restricciones

- **Solo CSS y DOM**, como hoy: nada de imágenes ni SVG externos. Las piezas nuevas (sombreros, ropa, lupa, monóculo, mano del naranja) son elementos dentro de cada `.crew-ch`, en unidades `--crew-u` para que escalen igual en el escenario y en la franja.
- **Animaciones creadas una vez por montaje**: setters `quickTo` o tweens y timelines en pausa que se reproducen o se reinician. Mover el ratón, escribir o fallar repetidamente nunca añade tweens al contexto de GSAP. Es la misma regla de la corrección de la Tarea 6 (`4bcba9c`).
- **Movimiento reducido:** los cuatro aparecen vestidos y quietos, el negro con la lupa en la mano y el naranja con su monóculo. No hay grieta ni cambio de monóculo.
- **Antes de hidratar** (`html.motion`): los personajes ya se pre-ocultan bajo el cristal de entrada actual. Las piezas nuevas viajan con su personaje, así que no necesitan reglas propias. El respaldo de 5 s de `globals.css` sigue cubriéndolas.
- **La franja móvil** mide 88 px de alto. Ahí los detalles pequeños pueden no leerse, y al builder le basta con que se distingan los sombreros. La grieta del monóculo se ve aunque sea pequeña.
- **Tamaño del CSS:** se cuenta con `pnpm css:audit` antes y después. Se anota en `docs/css-quality.md` y no debería pasar de unos 3 KB sin comprimir.
- `pnpm lint`, `pnpm lint:css`, `tsc`, `pnpm build` y `pnpm test:motion` siguen pasando.

## Decisiones del asistente (revisar)

- La rama sale de `main` después de fusionar el PR #7, porque toca el mismo archivo.
- La lupa se guarda también con el foco en el correo, no solo en la contraseña, como pidió el usuario ("mientras escribe el correo y la contraseña").
- El ojo agrandado es el del lado de la lupa, y se agranda escalando ese ojo (con su pupila) mientras está detrás del cristal.
- La mano del naranja que cambia el monóculo es nueva: el naranja hoy no tiene manos. Tiene la misma forma que las manos que tapan los ojos y su color se deriva del naranja.
- Con el foco en la contraseña, el azul y el negro se tapan los ojos como hoy. La lupa ya está guardada en ese momento, así que no estorba.
- Duraciones y curvas: se usan los tokens de `lib/motion/tokens.mjs`. `EASE.stick` (back.out) solo se aplica a los gestos de papel, como sacar o guardar la lupa y poner el monóculo.

## Lo que queda al builder

- El trazo exacto de cada prenda y pieza, dentro del estilo de papel recortado.
- Dónde exactamente sale y entra la lupa (bolsillo de la gabardina) y el recorrido de la mano del naranja.
- Cómo se dibuja la grieta (líneas en el cristal, un destello breve).

## Verificación

- A mano en escritorio (1280×800) y en móvil (375×667):
  - Con el foco en ningún campo, la lupa sigue al cursor.
  - Al enfocar el correo o la contraseña, la lupa se guarda, y vuelve a salir al quitar el foco.
  - Un error de inicio de sesión quiebra y cambia el monóculo. Dos errores seguidos reinician la secuencia limpiamente.
  - Con movimiento reducido todo queda quieto y vestido.
  - Sin JS, los personajes se ven vestidos.
- Tras un rato moviendo el ratón y fallando varias veces, el contexto de GSAP de los personajes no crece. Se comprueba igual que en la Tarea 6.
