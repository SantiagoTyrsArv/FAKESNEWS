"use client";

import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { pupilOffset } from "@/lib/motion/gaze.mjs";
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
const ENTER_DURATION = 1.1;
const ENTER_STAGGER = 0.12;
const STRETCH = 1.04;
const REACT_DURATION = 0.4;
const REACT_STAGGER = 0.05;
const AWAY = { x: -5, y: -4 };
const PEEK_X = -10;
const CARET_STEP = 8; // px per typed character, as a rough average glyph
const BLINK_MIN = 2000;
const BLINK_SPREAD = 4000;
const SHAKE_ROTATE = 3;
const FROWN_HOLD = 1.4;

type Point = { x: number; y: number };

type CrewApi = {
  apply: (state: CharacterState) => void;
  follow: (pointer: Point) => void;
  error: () => void;
};

/**
 * The four paper characters of the sign-in pages (decorative, aria-hidden).
 * They enter from below, follow the cursor (desktop, not `compact`), blink,
 * stretch toward the email field, cover or avert their eyes on the password,
 * peek when it is shown and shudder on an error. Reduced motion: still, eyes
 * front. The markup is a fixed pose, so the server render matches the client.
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
  const api = useRef<CrewApi | null>(null);
  const latest = useRef(state);
  const entered = useRef(false);

  useLayoutEffect(() => {
    latest.current = state;
  });

  useLayoutEffect(() => {
    const crew = ref.current;
    if (!ready || !crew || reduced) return;

    const timers = new Set<number>();
    let frame = 0;
    let pointer: Point | null = null;
    const track = !compact && !touch;

    const ctx = gsap.context(() => {
      const chars = gsap.utils.toArray<HTMLElement>(".crew-ch", crew);
      const byName = (name: string) =>
        chars.filter((c) => c.dataset.char === name);
      const striped = byName("striped");
      const hands = gsap.utils.toArray<HTMLElement>(".crew-hand", crew);
      const mouth = crew.querySelector<HTMLElement>(".crew-mouth");
      const unit = () => crew.offsetWidth / SCENE_WIDTH;
      const lean = LEAN_MAX * intensity;

      const pupilsOf = (c: HTMLElement) => c.querySelectorAll(".crew-pupil");
      const eyesOf = (c: HTMLElement) => c.querySelector(".crew-eyes");

      const setGaze = (c: HTMLElement, p: Point, duration = LOOK_DURATION) => {
        gsap.to(pupilsOf(c), { x: p.x, y: p.y, duration, ease: "power3.out", overwrite: "auto" });
        gsap.to(eyesOf(c), {
          x: p.x * EYES_FOLLOW,
          y: p.y * EYES_FOLLOW,
          duration: duration + 0.15,
          ease: "power3.out",
          overwrite: "auto",
        });
      };

      const setLean = (targets: HTMLElement[], skewX: number, x = 0) => {
        gsap.to(targets, { skewX, x, duration: LEAN_DURATION, ease: "power3.out", overwrite: "auto" });
      };

      // Every character looks at a point on the page and leans toward it.
      const lookAt = (target: Point) => {
        if (!crew.offsetWidth) return; // the other layout's crew (display: none)
        const u = unit();
        for (const c of chars) {
          const eyes = eyesOf(c);
          if (!eyes) continue;
          const r = eyes.getBoundingClientRect();
          const dx = target.x - (r.left + r.width / 2);
          const dy = target.y - (r.top + r.height / 2);
          setGaze(c, pupilOffset(dx, dy, PUPIL_MAX * u));
          const dist = Math.hypot(dx, dy) || 1;
          setLean([c], (-dx / dist) * Math.min(Math.abs(dx) / LEAN_RANGE, 1) * lean);
        }
      };

      const lookFront = () => {
        for (const c of chars) setGaze(c, { x: 0, y: 0 });
        setLean(chars, 0);
      };

      const setHands = (up: boolean) => {
        gsap.to(hands, {
          yPercent: up ? 0 : 160,
          y: 0,
          opacity: up ? 1 : 0,
          duration: REACT_DURATION,
          ease: up ? EASE.stick : "power2.in",
          stagger: 0.04,
          overwrite: "auto",
        });
      };

      const setStretch = (scaleY: number) => {
        gsap.to(chars, {
          scaleY,
          duration: REACT_DURATION,
          ease: EASE.stick,
          stagger: REACT_STAGGER,
          overwrite: "auto",
        });
      };

      // The focused field, at the end of what is typed in it.
      const fieldPoint = (caret: number): Point | null => {
        const el = document.activeElement;
        if (!(el instanceof HTMLElement) || el === document.body) return null;
        const r = el.getBoundingClientRect();
        return { x: r.left + 14 + Math.min(caret * CARET_STEP, r.width - 20), y: r.top + r.height / 2 };
      };

      const apply = (s: CharacterState) => {
        if (s.focus === "email") {
          setHands(false);
          setStretch(STRETCH);
          const p = fieldPoint(s.caret);
          if (p) lookAt(p);
        } else if (s.focus === "password") {
          const u = unit();
          setStretch(1);
          // The two at the back cover their eyes; everyone else looks away.
          setHands(true);
          for (const c of chars) {
            if (s.passwordVisible && striped.includes(c)) continue;
            setGaze(c, { x: AWAY.x * u, y: AWAY.y * u });
          }
          const others = chars.filter((c) => !(s.passwordVisible && striped.includes(c)));
          setLean(others, lean * 0.66);
          if (s.passwordVisible) {
            // The striped one leans out toward the form to spy.
            for (const c of striped) setGaze(c, { x: PUPIL_MAX * u, y: 4 * u }, 0.25);
            gsap.to(striped, {
              skewX: -lean,
              x: PEEK_X * u * intensity,
              duration: 0.5,
              ease: EASE.stick,
              overwrite: "auto",
            });
          }
        } else {
          setHands(false);
          setStretch(1);
          if (track && pointer) lookAt(pointer);
          else lookFront();
        }
      };

      const error = () => {
        const shake = scaled(SHAKE_ROTATE, intensity);
        gsap.fromTo(
          chars,
          { rotation: 0 },
          {
            rotation: shake,
            duration: 0.07,
            yoyo: true,
            repeat: 5,
            ease: "none",
            stagger: 0.03,
            onComplete: () => gsap.set(chars, { rotation: 0 }),
          },
        );
        if (mouth) {
          gsap
            .timeline()
            .to(mouth, { scaleY: -1, duration: 0.2, ease: "power2.out" })
            .to(mouth, { scaleY: 1, duration: 0.3, ease: "power2.out" }, `+=${FROWN_HOLD}`);
        }
      };

      // Called later from React effects and the pointer listener: whatever
      // they start belongs to this context and is reverted with it.
      api.current = {
        apply: (s) => ctx.add(() => apply(s)),
        follow: (p) => ctx.add(() => lookAt(p)),
        error: () => ctx.add(error),
      };

      if (entered.current) {
        gsap.set(chars, { y: 0, yPercent: 0 });
        apply(latest.current);
      } else {
        // From below, one after the other, like cutouts pasted onto the page.
        gsap.fromTo(
          chars,
          { y: 0, yPercent: 110 },
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
        apply(latest.current);
      }

      // Random blinks, each character on its own clock (client only).
      for (const c of chars) {
        const eyes = c.querySelectorAll(".crew-eye");
        const schedule = () => {
          const id = window.setTimeout(() => {
            timers.delete(id);
            ctx.add(() => {
              gsap.to(eyes, { scaleY: 0.1, duration: 0.07, yoyo: true, repeat: 1, ease: "power1.inOut" });
            });
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
  }, [ready, reduced, touch, compact, intensity]);

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

function Character({ name, hands = false, mouth = false }: { name: string; hands?: boolean; mouth?: boolean }) {
  return (
    <div className="crew-ch" data-char={name}>
      <div className="crew-body" />
      <div className="crew-eyes">
        <span className="crew-eye">
          <span className="crew-pupil" />
        </span>
        <span className="crew-eye">
          <span className="crew-pupil" />
        </span>
        {hands && (
          <span className="crew-hands">
            <span className="crew-hand" />
            <span className="crew-hand" />
          </span>
        )}
      </div>
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
