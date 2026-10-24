# Detective Characters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (the user asked for no subagents) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dress the four sign-in characters as detectives (option B), give the ink one a magnifier that follows the cursor and is pocketed while typing, and replace part of the error reaction with the orange one's monocle cracking and being swapped.

**Architecture:** Everything stays inside `AuthCharacters` (`apps/web/components/auth/characters.tsx`) and the `.crew*` CSS in `apps/web/app/globals.css`. The clothes are static DOM pieces inside each `.crew-ch`, drawn in `--crew-u` units, so the server pose already shows them dressed. The two new behaviours are created once per mount in the existing `gsap.context`: a `quickTo` setter for the lens plus a paused "pocket" tween, and a paused "monocle" timeline that restarts on every error. The lens tilt math is a pure function in `lib/motion/gaze.mjs`, so it can be tested.

**Tech Stack:** Next 16 / React 19 client component, GSAP 3 (`gsap.quickTo`, paused tweens/timelines), Tailwind 4 + plain CSS in `globals.css`, `node:test` for the `.mjs` helpers.

**Spec:** `docs/superpowers/specs/2026-10-24-detective-characters-design.md`

## Global Constraints

- CSS and DOM only, no images or external SVG. New pieces are elements inside each `.crew-ch`, sized in `--crew-u` units.
- Animations are created once per mount (`quickTo` setters, paused tweens/timelines played or restarted). Moving the mouse, typing or failing repeatedly never adds tweens to the GSAP context.
- Reduced motion: all four show dressed and still, ink with the magnifier in hand, orange with its monocle. No crack, no swap.
- The characters stay decorative (`aria-hidden`), and the server markup is a fixed pose identical to the client's.
- Existing behaviours are unchanged: entrance from below, blinking, cursor tracking, stretch toward email, blue and ink covering their eyes on the password, the striped one peeking, the shudder, the frowning mouth and the form bounce.
- The compact mobile strip is 88 px tall. There it is enough that the hats are distinguishable, and the monocle crack still plays.
- CSS growth stays around 3 KB uncompressed (`pnpm css:audit`, before/after recorded in `docs/css-quality.md`).
- Tokens come from `lib/motion/tokens.mjs`. `EASE.stick` is used only for paper gestures (lens out/in, monocle on).
- New colours are CSS variables next to `.crew` in `globals.css`. The palette is: gabardine beige, check brown, tie/scarf red, monocle/lens gold.
- `pnpm lint`, `pnpm lint:css`, `pnpm exec tsc --noEmit`, `pnpm build` and `pnpm test:motion` pass after every task.

## Review Focus

- **An error while the lens is pocketed** (Enter from the password field): only the monocle reacts, and the lens stays in the pocket. Task 3 checks this by hand.
- **Two errors in quick succession:** the monocle timeline restarts cleanly. It never ends with no monocle or with two. Task 3 checks this.
- **Leaving a field to nowhere** (focus `none`) brings the lens out exactly once, even when focus moves email → password directly (no in-between `none`). Task 2 checks this.
- **Resizing across `lg`** swaps stage ↔ strip. The other copy mounts dressed, with the lens in hand and the monocle on, and none of the old copy's state leaks. Task 2 checks this.
- **Reduced motion toggled at runtime** (effect re-runs): the context reverts to the dressed static pose with no half-cracked monocle. Task 3 checks this.

---

### Task 1: Detective wardrobe (static)

**Files:**
- Modify: `apps/web/components/auth/characters.tsx` (the `Character` component and the four call sites in `AuthCharacters`)
- Modify: `apps/web/app/globals.css` (the `.crew*` block)
- Modify: `docs/css-quality.md` (record before/after)

**Interfaces:**
- Produces (DOM contract used by Tasks 2–3):
  - `.crew-ch[data-char="ink"] .crew-lens`: the magnifier group (handle + glass). Its pivot (`transform-origin`) is at the hand end of the handle, and at rest it sits in front of ink's right eye.
  - `.crew-ch[data-char="ink"] .crew-eye[data-lens-eye]`: the eye behind the glass.
  - `.crew-ch[data-char="orange"] .crew-monocle`: the monocle on orange's right eye, holding a `.crew-crack` child (hidden at rest, `opacity: 0`).
  - `.crew-ch[data-char="orange"] .crew-paw`: orange's new hand, hidden at rest like `.crew-hand` (`opacity: 0`, translated down).
- `Character` gains a `name`-driven wardrobe. Either a `wardrobe` switch inside `Character` or explicit children per call site works; pick one and keep `Character` the only place that renders a character.

- [ ] **Step 1:** Run `pnpm build && pnpm css:audit` in `apps/web` and note the home CSS bytes (raw and gzip) for the docs.
- [ ] **Step 2:** Add the pieces per the spec table:
  - **Ink:** fedora with red band, beige gabardine with lapels, red tie, belt, and the lens group in hand.
  - **Blue:** check deerstalker with both peaks, red scarf.
  - **Striped:** grey newsboy cap with button and peak, yellow pencil behind the ear.
  - **Orange:** black bowler, gold monocle with cord, hidden paw.
  
  Hats sit on top of each body and may overflow the body box (`.crew-ch` must not clip them). The tall `.crew` aspect box already has headroom; check the blue deerstalker isn't clipped by `.crew-box`/`aside` overflow. The approved sketch for proportions is `.superpowers/brainstorm/1763-1792857983/content/detectives-estilo.html`, option B.
- [ ] **Step 3:** In `globals.css`, add the colour variables next to `.crew` and the piece rules, all in `calc(N * var(--crew-u))`. The existing `.crew-hands` cover-the-eyes hands must still render above ink's lens when raised (z-order inside `.crew-eyes`).
- [ ] **Step 4:** Run `pnpm lint && pnpm lint:css && pnpm exec tsc --noEmit && pnpm test:motion && pnpm build`. Expected: all pass.
- [ ] **Step 5:** Visual check with `pnpm start -p 3100` and Playwright screenshots of `/login` at 1280×800 and 375×667, plus 1280×800 with `reducedMotion: "reduce"` and 1280×800 with JavaScript disabled. Expected: the four characters appear dressed in all three, with the hats readable in the strip. The lens and the monocle are visible, and nothing is clipped. Then stop that server by its PID, never with a global node kill.
- [ ] **Step 6:** Run `pnpm css:audit`, add a dated "Personajes detective" line to `docs/css-quality.md` with before → after (raw and gzip). Expected growth is about 3 KB raw at most; if it's over, say so in the line.
- [ ] **Step 7:** Commit: `feat(web): dress the sign-in characters as detectives`.

### Task 2: The magnifier follows the cursor and is pocketed while typing

**Files:**
- Modify: `apps/web/lib/motion/gaze.mjs`, `apps/web/lib/motion/gaze.test.mjs`
- Modify: `apps/web/components/auth/characters.tsx` (inside the existing `gsap.context` in the main `useLayoutEffect`)

**Interfaces:**
- Consumes: the `.crew-lens` and `.crew-eye[data-lens-eye]` from Task 1, plus `lookAt(target)`, `lookFront()` and `apply(state)` in `AuthCharacters`.
- Produces: `export function lensTilt(dx, max)` in `gaze.mjs`, returning `number` (degrees) = `max × clamp(dx / 240, -1, 1)`. 240 px is the lens range constant, `LENS_RANGE`.

- [ ] **Step 1: Write the failing tests** in `gaze.test.mjs`:

```js
test("lensTilt: straight ahead is 0", () => {
  assert.equal(lensTilt(0, 30), 0);
});
test("lensTilt: scales with dx / 240", () => {
  assert.equal(lensTilt(120, 30), 15);
});
test("lensTilt: caps at ±max", () => {
  assert.equal(lensTilt(-1000, 30), -30);
  assert.equal(lensTilt(1000, 30), 30);
});
```

- [ ] **Step 2:** Run `pnpm test:motion`. Expected: FAIL, `lensTilt` is not exported.
- [ ] **Step 3:** Implement `lensTilt(dx, max)` in `gaze.mjs`, with a JSDoc comment like `pupilOffset`'s.
- [ ] **Step 4:** Run `pnpm test:motion`. Expected: PASS (14 tests).
- [ ] **Step 5:** In `AuthCharacters`, inside the context and once per mount:
  - `lensRotate = gsap.quickTo(lens, "rotation", look)` (lens tilt max `LENS_TILT = 30`, scaled by `intensity`).
  - `lensX`/`lensY` quickTo, driven by `pupilOffset` with `max = 6 * unit()`, so the glass drifts toward the cursor.
  - A paused `pocket` tween (lens `yPercent` down into the gabardine plus `opacity: 0`, `REACT_DURATION`, `EASE.stick`) and a matching paused scale on the `[data-lens-eye]` eye (1 → 1.35 while the lens is out).
  
  In `lookAt`, aim the lens from ink's lens eye. In `lookFront`, aim it to 0. In `apply`, `pocket.play()` when focus is `email` or `password`, and `pocket.reverse()` when `none`. Because these are play/reverse of one tween, email → password without a `none` between stays pocketed (Review Focus). Reduced motion never runs this effect, so the static pose of Task 1 applies.
- [ ] **Step 6:** Run `pnpm lint && pnpm exec tsc --noEmit && pnpm build`. Expected: pass.
- [ ] **Step 7:** Manual check on `pnpm start -p 3100`, Playwright at 1280×800 on `/login`:
  - Move the mouse left and right of ink: the lens tilts and drifts toward the cursor, and the eye stays enlarged.
  - Focus email: pocketed. Tab to password: still pocketed. Blur by clicking empty space: the lens comes out.
  - Resize to 375 px and back to 1280: the new copy shows the lens in hand.
  - Code check: `lookAt`, `lookFront`, `apply`, `onMove` and the error handler call only `quickTo` setters and `play`/`reverse`/`restart`, never `gsap.to`/`from`/`fromTo`/`timeline`/`set` or `ctx.add`. That is what keeps the context from growing.
- [ ] **Step 8:** Commit: `feat(web): let the detective aim his magnifier and pocket it while typing`.

### Task 3: The monocle cracks and is swapped on an error

**Files:**
- Modify: `apps/web/components/auth/characters.tsx` (the `failure` timeline setup)

**Interfaces:**
- Consumes: `.crew-monocle`, `.crew-crack` and `.crew-paw` from Task 1, plus the existing `failure` paused timeline restarted by `api.current.error()`.
- Produces: nothing new outside the component.

- [ ] **Step 1:** Extend the existing paused `failure` timeline (don't create a second one), so one `failure.restart()` drives shudder, frown and monocle together. Total ≈ 1.5 s:
  - **0–0.15 s:** `.crew-crack` opacity 0 → 1 plus a quick flash.
  - **~0.3 s:** `.crew-paw` rises (`EASE.stick`), takes the cracked monocle off (monocle moves down with the paw, `opacity` → 0).
  - **~0.8 s:** the paw comes back up with a fresh monocle (crack reset to `opacity: 0`, monocle back in place, `EASE.stick`).
  - **~1.3–1.5 s:** the paw lowers out of view.
  
  Every property the timeline touches has an explicit `fromTo` start, so a restart mid-way always begins from a clean, monocle-on state (Review Focus: two errors in a row).
- [ ] **Step 2:** Run `pnpm lint && pnpm exec tsc --noEmit && pnpm build`. Expected: pass.
- [ ] **Step 3:** Manual check on `pnpm start -p 3100` with the API down, so every sign-in fails. Playwright on `/login` at 1280×800 and 375×667:
  - **One failed submit:** the crack, then the swap, and the monocle ends on. The lens stays pocketed when the submit came from the password field (Enter).
  - **Two submits 0.4 s apart:** a clean restart, ending with exactly one monocle visible.
  - **Toggle `reducedMotion` to `reduce` mid-session** (`page.emulateMedia`): the static dressed pose, with no crack visible.
  - Code check: the error path only calls `failure.restart()`.
- [ ] **Step 4:** Commit: `feat(web): crack and swap the orange detective's monocle on an error`.
