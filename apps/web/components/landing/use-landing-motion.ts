"use client";

import { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { isDocumentLoad } from "@/lib/motion/document";
import { onceInSession } from "@/lib/motion/env.mjs";
import { gsap, SplitText } from "@/lib/motion/gsap";
import { DURATION, EASE, STAGGER, scaled } from "@/lib/motion/tokens.mjs";

// Same query as the `[data-enter]` pre-hide in globals.css: only where CSS hid
// the hero blocks does the entrance animate them from hidden.
const DESKTOP = "(prefers-reduced-motion: no-preference) and (hover: hover) and (pointer: fine)";

const ENTRANCE_MAX = 1.5; // the whole entrance, curtain included
const CURTAIN_TOTAL = 0.9;
const CURTAIN_STAGGER = 0.08;
const CURTAIN_LEAD = 0.2; // the header starts while the curtain is still lifting
const LINE_ROTATE = 4;
const TITLE_DURATION = 1.1;
const CARD_DROP = 80;
const CARD_ROTATE = -9;
const CARD_DURATION = 1.2;
const POP_SCALE = 0.96;
const POP_TOTAL = 0.4;
const PARALLAX = 10;
// Enough overscan that a ±10% shift never shows the image's edges.
const PARALLAX_SCALE = 1.22;
const MARK_START = "mark-go";

/**
 * The landing page's motion: the entrance timeline (curtain once per session,
 * header, kicker, title line by line, lede, actions, collage, the example card
 * pasted on, then the verdict marks), section titles line by line on scroll and
 * the step illustrations' parallax. On a client navigation back to `/` the
 * entrance is a quick pop. Whatever happens (unmount mid-entrance included),
 * the hero blocks end visible.
 */
export function useLandingMotion(root: RefObject<HTMLElement | null>) {
  const { reduced, touch, intensity, ready } = useMotion();
  const [documentLoad] = useState(isDocumentLoad);
  // The entrance plays once per mount, not again when the motion env changes.
  const entered = useRef(false);

  useLayoutEffect(() => {
    const el = root.current;
    if (!ready || !el) return;

    const one = (selector: string) => el.querySelector<HTMLElement>(selector);
    const enterEls = gsap.utils.toArray<HTMLElement>("[data-enter]", el);
    const startMarks = () =>
      el.querySelectorAll(".mark-draw").forEach((m) => m.classList.add(MARK_START));

    let entrance: gsap.core.Timeline | undefined;
    if (entered.current) {
      gsap.set(enterEls, { opacity: 1 });
      startMarks();
    } else {
      entered.current = true;
      const desktop = window.matchMedia(DESKTOP).matches;
      if (!desktop) {
        // Touch / reduced motion: nothing was pre-hidden and the title stays put.
        startMarks();
      } else if (!documentLoad) {
        entrance = pop(enterEls, startMarks);
      } else {
        const curtain = one("[data-curtain]");
        const showCurtain = !!curtain && onceInSession("fn-curtain", sessionStorage);
        entrance = choreograph(el, showCurtain ? curtain : null, intensity, startMarks);
      }
    }

    const ctx = gsap.context(() => {
      if (reduced) return;

      // Section titles rise line by line from a mask as they scroll in.
      for (const h2 of gsap.utils.toArray<HTMLElement>("h2", el)) {
        SplitText.create(h2, {
          type: "lines",
          mask: "lines",
          autoSplit: true,
          onSplit: (self) =>
            gsap.from(self.lines, {
              yPercent: 110,
              rotation: scaled(LINE_ROTATE, intensity),
              transformOrigin: "0% 100%",
              duration: DURATION.enter,
              ease: EASE.out,
              stagger: scaled(STAGGER.base, intensity),
              scrollTrigger: { trigger: h2, start: "clamp(top 85%)", once: true },
            }),
        });
      }

      // Step illustrations drift inside their cutout.
      for (const img of gsap.utils.toArray<HTMLElement>("[data-parallax]", el)) {
        gsap.fromTo(
          img,
          { yPercent: -PARALLAX * intensity, scale: PARALLAX_SCALE },
          {
            yPercent: PARALLAX * intensity,
            scale: PARALLAX_SCALE,
            ease: "none",
            scrollTrigger: {
              trigger: img.parentElement ?? img,
              start: "top bottom",
              end: "bottom top",
              scrub: true,
            },
          },
        );
      }
    }, el);

    return () => {
      // Jump to the end (callbacks included): blocks visible, title split
      // reverted, curtain gone, marks drawing.
      entrance?.progress(1).kill();
      ctx.revert();
    };
  }, [root, ready, reduced, touch, intensity, documentLoad]);
}

/** Client navigation back to `/`: the hero blocks pop in within 400 ms. */
function pop(els: HTMLElement[], onComplete: () => void) {
  const stagger = Math.min(
    STAGGER.pop,
    els.length > 1 ? (POP_TOTAL - DURATION.pop) / (els.length - 1) : 0,
  );
  return gsap.timeline({ onComplete }).fromTo(
    els,
    { opacity: 0, scale: POP_SCALE },
    {
      opacity: 1,
      scale: 1,
      duration: DURATION.pop,
      ease: EASE.stick,
      stagger,
      clearProps: "transform",
    },
  );
}

/** The document load of `/` on desktop: the full entrance, ≤ 1.5 s. */
function choreograph(
  root: HTMLElement,
  curtain: HTMLElement | null,
  intensity: number,
  onComplete: () => void,
) {
  const one = (name: string) => root.querySelector<HTMLElement>(`[data-enter="${name}"]`);
  const s = (v: number) => scaled(v, intensity);
  const tl = gsap.timeline({ defaults: { ease: EASE.out }, onComplete });

  let at = 0;
  if (curtain) {
    gsap.set(curtain, { display: "flex" });
    tl.fromTo(
      curtain.children,
      { yPercent: 0 },
      {
        yPercent: -100,
        duration: CURTAIN_TOTAL - CURTAIN_STAGGER * (curtain.children.length - 1),
        ease: "power4.inOut",
        stagger: CURTAIN_STAGGER,
      },
      0,
    );
    tl.set(curtain, { display: "none" });
    at = CURTAIN_LEAD;
  }

  const rise = (target: HTMLElement | null, y: number, position: number, duration = 0.6) => {
    if (!target) return;
    tl.fromTo(
      target,
      { opacity: 0, y },
      { opacity: 1, y: 0, duration, clearProps: "transform" },
      at + position,
    );
  };

  rise(one("header"), s(-20), 0);
  rise(one("kicker"), s(16), 0.06);

  // The title is never hidden before hydration (LCP): its lines drop behind a
  // mask on already painted text and rise back.
  const title = root.querySelector<HTMLElement>("h1");
  if (title) {
    const split = SplitText.create(title, { type: "lines", mask: "lines" });
    tl.fromTo(
      split.lines,
      { yPercent: 110, rotation: s(LINE_ROTATE) },
      {
        yPercent: 0,
        rotation: 0,
        transformOrigin: "0% 100%",
        duration: TITLE_DURATION,
        stagger: s(STAGGER.base),
        onComplete: () => split.revert(),
      },
      at + 0.1,
    );
  }

  rise(one("lede"), s(20), 0.18, 0.8);
  // The actions' wrapper bounces in (the buttons themselves carry CSS
  // transitions and the magnetic pull).
  const actions = one("actions");
  if (actions) {
    tl.fromTo(
      actions,
      { opacity: 0, y: s(16) },
      { opacity: 1, y: 0, duration: 0.6, ease: EASE.stick, clearProps: "transform" },
      at + 0.24,
    );
  }

  // The collage is the LCP image: never hidden, only a slight settle.
  const collage = root.querySelector<HTMLElement>("[data-collage]");
  if (collage) {
    tl.fromTo(
      collage,
      { scale: 0.98 },
      { scale: 1, duration: 0.9, clearProps: "transform" },
      at + 0.2,
    );
  }

  // The example card falls tilted and sticks at its cutout angle. Its wrapper
  // carries the drop, so the card's own tilt (data-tilt) stays untouched.
  const card = one("card");
  if (card) {
    const cutout = card.querySelector<HTMLElement>(".cutout");
    const rest = cutout
      ? Number.parseFloat(getComputedStyle(cutout).getPropertyValue("--cutout-rotate")) || 0
      : 0;
    tl.fromTo(
      card,
      { opacity: 0, y: s(CARD_DROP), rotation: s(CARD_ROTATE) - rest },
      {
        opacity: 1,
        y: 0,
        rotation: 0,
        duration: CARD_DURATION,
        ease: "back.out(1.2)",
        clearProps: "transform",
      },
      at + 0.3,
    );
  }

  if (tl.duration() > ENTRANCE_MAX) tl.timeScale(tl.duration() / ENTRANCE_MAX);
  return tl;
}
