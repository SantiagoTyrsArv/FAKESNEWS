"use client";

import { useEffect, useLayoutEffect, useRef, useSyncExternalStore, type ReactNode, type RefObject } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { lensTilt, pupilOffset } from "@/lib/motion/gaze.mjs";
import { gsap } from "@/lib/motion/gsap";
import { EASE, scaled } from "@/lib/motion/tokens.mjs";

export type CharacterState = {
  focus: "none" | "email" | "password";
  passwordVisible: boolean;
  /** Characters typed in the email field: the gaze follows it along. */
  caret: number;
  /** Incremented on every new error; 0 means none yet. */
  errorKey: number;
};

// The scene is drawn 460 px wide (globals.css, `.crew`); pixel amounts below
// are in that scale and multiplied by the rendered size.
const SCENE_WIDTH = 460;
const PUPIL_MAX = 5;
const EYES_FOLLOW = 1.4; // the whole pair of eyes drifts a bit further than the pupils
const LEAN_MAX = 6; // degrees, at intensity 1
const LEAN_RANGE = 500; // px of horizontal distance for the full lean
const LOOK_DURATION = 0.35;
const LEAN_DURATION = 0.8;
const PEEK_DURATION = 0.5;
const ENTER_DURATION = 1.1;
const ENTER_STAGGER = 0.12;
// Matches the CSS pre-hide: low enough that the hats start below the stage.
const ENTER_FROM = 130;
const STRETCH = 1.04;
const REACT_DURATION = 0.4;
const REACT_STAGGER = 0.05;
const AWAY = { x: -5, y: -4 };
const PEEK = { x: 5, y: 4 };
const PEEK_X = -10;
const CARET_STEP = 8; // px per typed character, as a rough average glyph
const BLINK_MIN = 2000;
const BLINK_SPREAD = 4000;
const SHAKE_ROTATE = 3;
const FROWN_HOLD = 1.4;
const LENS_TILT = 30; // degrees, at intensity 1
const LENS_DRIFT = 6; // scene px the glass slides toward the target
const LENS_ZOOM = 1.6; // the pupil behind the glass
const LENS_POCKET = 180; // yPercent: down into the gabardine

// AuthShell shows the full stage from Tailwind's `lg` up and the compact strip
// below it; only the copy on screen animates.
const DESKTOP_LAYOUT = "(min-width: 64rem)";

type Point = { x: number; y: number };

type CrewApi = {
  apply: (state: CharacterState) => void;
  follow: (pointer: Point) => void;
  error: () => void;
};

// One character's continuous setters, built once per mount: every look and
// lean retargets the same tween instead of creating new ones.
type Rig = {
  el: HTMLElement;
  eyes: HTMLElement;
  striped: boolean;
  pupilX: gsap.QuickToFunc;
  pupilY: gsap.QuickToFunc;
  eyesX: gsap.QuickToFunc;
  eyesY: gsap.QuickToFunc;
  skew: gsap.QuickToFunc;
  shift: gsap.QuickToFunc;
};

function subscribeLayout(onChange: () => void) {
  const m = window.matchMedia(DESKTOP_LAYOUT);
  m.addEventListener("change", onChange);
  return () => m.removeEventListener("change", onChange);
}

/** Whether this copy (stage or strip) is the one AuthShell displays. */
function useOnScreen(compact: boolean) {
  const desktop = useSyncExternalStore(
    subscribeLayout,
    () => window.matchMedia(DESKTOP_LAYOUT).matches,
    () => null,
  );
  return desktop !== null && desktop !== compact;
}

/**
 * The four paper characters of the sign-in pages (decorative, aria-hidden).
 * They enter from below, follow the cursor (desktop, not `compact`), blink,
 * stretch toward the email field, cover or avert their eyes on the password,
 * peek when it is shown and shudder on an error. Reduced motion: still, eyes
 * front. The markup is a fixed pose, so the server render matches the client.
 *
 * Every animation is created once per mount (setters, paused timelines played
 * forward/back or restarted), so moving the mouse, typing, blinking or failing
 * again never adds tweens to the context.
 */
export function AuthCharacters({
  state,
  compact = false,
}: {
  state: CharacterState;
  compact?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const { reduced, touch, intensity, ready } = useMotion();
  const onScreen = useOnScreen(compact);
  const api = useRef<CrewApi | null>(null);
  const latest = useRef(state);
  const entered = useRef(false);

  useLayoutEffect(() => {
    latest.current = state;
  });

  useLayoutEffect(() => {
    const crew = ref.current;
    if (!ready || !crew || reduced || !onScreen) return;

    const timers = new Set<number>();
    let frame = 0;
    let pointer: Point | null = null;
    const track = !compact && !touch;

    const ctx = gsap.context(() => {
      const chars = gsap.utils.toArray<HTMLElement>(".crew-ch", crew);
      const hands = gsap.utils.toArray<HTMLElement>(".crew-hand", crew);
      const mouth = crew.querySelector<HTMLElement>(".crew-mouth");
      const unit = () => crew.offsetWidth / SCENE_WIDTH;
      const lean = LEAN_MAX * intensity;
      const look = { duration: LOOK_DURATION, ease: "power3.out" };

      const rigs: Rig[] = chars.map((el) => {
        const eyes = el.querySelector<HTMLElement>(".crew-eyes")!;
        const pupils = el.querySelectorAll(".crew-pupil");
        return {
          el,
          eyes,
          striped: el.dataset.char === "striped",
          pupilX: gsap.quickTo(pupils, "x", look),
          pupilY: gsap.quickTo(pupils, "y", look),
          eyesX: gsap.quickTo(eyes, "x", { ...look, duration: LOOK_DURATION + 0.15 }),
          eyesY: gsap.quickTo(eyes, "y", { ...look, duration: LOOK_DURATION + 0.15 }),
          skew: gsap.quickTo(el, "skewX", { duration: LEAN_DURATION, ease: "power3.out" }),
          shift: gsap.quickTo(el, "x", { duration: PEEK_DURATION, ease: "power3.out" }),
        };
      });

      // The detective's magnifier: aimed by two setters and a tilt setter,
      // pocketed and brought out by one paused timeline.
      const lens = crew.querySelector<HTMLElement>(".crew-lens");
      const lensEye = crew.querySelector<HTMLElement>("[data-lens-eye]");
      const lensPupil = lensEye?.querySelector<HTMLElement>(".crew-pupil") ?? null;
      const lensRotate = lens ? gsap.quickTo(lens, "rotation", look) : null;
      const lensX = lens ? gsap.quickTo(lens, "x", look) : null;
      const lensY = lens ? gsap.quickTo(lens, "y", look) : null;
      const aimLens = (dx: number, dy: number, u: number) => {
        lensRotate?.(lensTilt(dx, LENS_TILT * intensity));
        const drift = pupilOffset(dx, dy, LENS_DRIFT * u);
        lensX?.(drift.x);
        lensY?.(drift.y);
      };
      if (lensPupil) gsap.set(lensPupil, { scale: LENS_ZOOM });
      const pocket = gsap.timeline({ paused: true, defaults: { duration: REACT_DURATION, ease: EASE.stick } });
      if (lens) pocket.to(lens, { yPercent: LENS_POCKET, opacity: 0 }, 0);
      if (lensPupil) pocket.to(lensPupil, { scale: 1 }, 0);
      const setPocket = (pocketed: boolean) => (pocketed ? pocket.play() : pocket.reverse());

      const gaze = (r: Rig, p: Point) => {
        r.pupilX(p.x);
        r.pupilY(p.y);
        r.eyesX(p.x * EYES_FOLLOW);
        r.eyesY(p.y * EYES_FOLLOW);
      };

      const pose = (r: Rig, skewX: number, x = 0) => {
        r.skew(skewX);
        r.shift(x);
      };

      // Every character looks at a point on the page and leans toward it.
      const lookAt = (target: Point) => {
        const u = unit();
        if (lensEye) {
          const box = lensEye.getBoundingClientRect();
          aimLens(target.x - (box.left + box.width / 2), target.y - (box.top + box.height / 2), u);
        }
        for (const r of rigs) {
          const box = r.eyes.getBoundingClientRect();
          const dx = target.x - (box.left + box.width / 2);
          const dy = target.y - (box.top + box.height / 2);
          gaze(r, pupilOffset(dx, dy, PUPIL_MAX * u));
          const dist = Math.hypot(dx, dy) || 1;
          pose(r, (-dx / dist) * Math.min(Math.abs(dx) / LEAN_RANGE, 1) * lean);
        }
      };

      const lookFront = () => {
        aimLens(0, 0, unit());
        for (const r of rigs) {
          gaze(r, { x: 0, y: 0 });
          pose(r, 0);
        }
      };

      // Hands over the eyes and the curious stretch: one paused animation
      // each, played forward or back.
      gsap.set(hands, { y: 0, yPercent: 160, opacity: 0 });
      const handsUp = gsap.to(hands, {
        yPercent: 0,
        opacity: 1,
        duration: REACT_DURATION,
        ease: EASE.stick,
        stagger: 0.04,
        paused: true,
      });
      const stretch = gsap.to(chars, {
        scaleY: STRETCH,
        duration: REACT_DURATION,
        ease: EASE.stick,
        stagger: REACT_STAGGER,
        paused: true,
      });
      const setHands = (up: boolean) => (up ? handsUp.play() : handsUp.reverse());
      const setStretch = (on: boolean) => (on ? stretch.play() : stretch.reverse());

      // The error: a short shudder (about 0.4 s) and the mouth upside down
      // for 1.4 s. Restarted on every new error.
      const shake = scaled(SHAKE_ROTATE, intensity);
      const failure = gsap.timeline({ paused: true });
      failure.fromTo(
        chars,
        { rotation: 0 },
        { rotation: shake, duration: 0.07, yoyo: true, repeat: 5, ease: "none", stagger: 0.03 },
        0,
      );
      if (mouth) {
        failure
          .fromTo(mouth, { scaleY: 1 }, { scaleY: -1, duration: 0.2, ease: "power2.out" }, 0)
          .to(mouth, { scaleY: 1, duration: 0.3, ease: "power2.out" }, 0.2 + FROWN_HOLD);
      }

      // The focused field, at the end of what is typed in it.
      const fieldPoint = (caret: number): Point | null => {
        const el = document.activeElement;
        if (!(el instanceof HTMLElement) || el === document.body) return null;
        const r = el.getBoundingClientRect();
        return { x: r.left + 14 + Math.min(caret * CARET_STEP, r.width - 20), y: r.top + r.height / 2 };
      };

      const apply = (s: CharacterState) => {
        setPocket(s.focus !== "none");
        if (s.focus === "email") {
          setHands(false);
          setStretch(true);
          const p = fieldPoint(s.caret);
          if (p) lookAt(p);
        } else if (s.focus === "password") {
          const u = unit();
          setStretch(false);
          // The two at the back cover their eyes; everyone else looks away.
          setHands(true);
          for (const r of rigs) {
            if (s.passwordVisible && r.striped) {
              // The striped one leans out toward the form to spy.
              gaze(r, { x: PEEK.x * u, y: PEEK.y * u });
              pose(r, -lean, PEEK_X * u * intensity);
            } else {
              gaze(r, { x: AWAY.x * u, y: AWAY.y * u });
              pose(r, lean * 0.66);
            }
          }
        } else {
          setHands(false);
          setStretch(false);
          if (track && pointer) lookAt(pointer);
          else lookFront();
        }
      };

      api.current = {
        apply,
        follow: lookAt,
        error: () => failure.restart(),
      };

      if (entered.current) {
        gsap.set(chars, { y: 0, yPercent: 0 });
      } else {
        // From below, one after the other, like cutouts pasted onto the page.
        gsap.fromTo(
          chars,
          { y: 0, yPercent: ENTER_FROM },
          {
            yPercent: 0,
            duration: ENTER_DURATION,
            ease: EASE.stick,
            stagger: scaled(ENTER_STAGGER, intensity),
            onComplete: () => {
              entered.current = true;
            },
          },
        );
      }
      apply(latest.current);

      // Random blinks, each character on its own clock (client only); each
      // blink replays that character's one paused tween.
      for (const c of chars) {
        const blink = gsap.to(c.querySelectorAll(".crew-eye"), {
          scaleY: 0.1,
          duration: 0.07,
          yoyo: true,
          repeat: 1,
          ease: "power1.inOut",
          paused: true,
        });
        const schedule = () => {
          const id = window.setTimeout(() => {
            timers.delete(id);
            blink.restart();
            schedule();
          }, BLINK_MIN + Math.random() * BLINK_SPREAD);
          timers.add(id);
        };
        schedule();
      }
    }, crew);

    // One listener for the whole stage, at most one look per frame.
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      pointer = { x: e.clientX, y: e.clientY };
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        if (latest.current.focus === "none" && pointer) api.current?.follow(pointer);
      });
    };
    if (track) window.addEventListener("pointermove", onMove, { passive: true });

    return () => {
      if (track) window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(frame);
      timers.forEach((id) => window.clearTimeout(id));
      api.current = null;
      ctx.revert();
    };
  }, [ready, reduced, touch, compact, intensity, onScreen]);

  // Reactions to the form: focus, typing, the show-password toggle.
  const { focus, passwordVisible, caret, errorKey } = state;
  useEffect(() => {
    api.current?.apply(latest.current);
  }, [focus, passwordVisible, caret]);

  // A new error (0 is "none yet").
  useEffect(() => {
    if (errorKey > 0) api.current?.error();
  }, [errorKey]);

  return (
    <div ref={ref} aria-hidden="true" className="crew">
      <Character name="blue" hands />
      <Character name="ink" hands />
      <Character name="striped" />
      <Character name="orange" mouth />
    </div>
  );
}

type CharacterName = "blue" | "ink" | "striped" | "orange";

// Each one's detective outfit (globals.css draws the pieces): the pieces that
// sit on the body go before the eyes, the ones held over the face after them.
const OUTFIT: Record<CharacterName, { body: ReactNode; face?: ReactNode }> = {
  ink: {
    body: (
      <>
        <span className="crew-coat" />
        <span className="crew-tie" />
        <span className="crew-hat" />
      </>
    ),
    face: <span className="crew-lens" />,
  },
  blue: {
    body: (
      <>
        <span className="crew-scarf" />
        <span className="crew-hat" />
      </>
    ),
  },
  striped: {
    body: (
      <>
        <span className="crew-hat" />
        <span className="crew-pencil" />
      </>
    ),
  },
  orange: {
    body: <span className="crew-hat" />,
    face: (
      <>
        <span className="crew-monocle">
          <span className="crew-crack" />
        </span>
        <span className="crew-paw" />
      </>
    ),
  },
};

function Character({
  name,
  hands = false,
  mouth = false,
}: {
  name: CharacterName;
  hands?: boolean;
  mouth?: boolean;
}) {
  const outfit = OUTFIT[name];
  return (
    <div className="crew-ch" data-char={name}>
      <div className="crew-body" />
      {outfit.body}
      <div className="crew-eyes">
        <span className="crew-eye">
          <span className="crew-pupil" />
        </span>
        <span className="crew-eye" data-lens-eye={name === "ink" ? "" : undefined}>
          <span className="crew-pupil" />
        </span>
        {hands && (
          <span className="crew-hands">
            <span className="crew-hand" />
            <span className="crew-hand" />
          </span>
        )}
      </div>
      {outfit.face}
      {mouth && <span className="crew-mouth" />}
    </div>
  );
}

/**
 * The form's small horizontal bounce on a new error (≤ 8 px, so the focused
 * field stays under the caret). Nothing with reduced motion.
 */
export function useErrorBounce(form: RefObject<HTMLElement | null>, errorKey: number) {
  const { reduced } = useMotion();
  useEffect(() => {
    const el = form.current;
    if (!el || errorKey === 0 || reduced) return;
    const tween = gsap.fromTo(
      el,
      { x: -8 },
      { x: 0, duration: 0.5, ease: "elastic.out(1, 0.3)", clearProps: "transform" },
    );
    return () => {
      tween.kill();
      gsap.set(el, { clearProps: "transform" });
    };
  }, [form, errorKey, reduced]);
}
