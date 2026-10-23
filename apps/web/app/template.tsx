"use client";

import { usePathname } from "next/navigation";
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { attachMagnetic, attachTilt } from "@/lib/motion/interactions";
import { gsap, ScrollTrigger } from "@/lib/motion/gsap";
import { DURATION, EASE, STAGGER, scaled } from "@/lib/motion/tokens.mjs";

// The root template remounts whenever the first URL segment changes (Next docs,
// template.js); this flag tells the first mount of the document apart.
let documentMounted = false;

const POP_SCALE = 0.96;
const POP_TOTAL = 0.4; // every first-screen pop is done within 400 ms
const REVEAL_DISTANCE = 40;
const REVEAL_DURATION = 0.8;
const ANIMATED = "[data-pop], [data-reveal]";

function inFirstScreen(el: Element) {
  const r = el.getBoundingClientRect();
  return r.bottom > 0 && r.top < window.innerHeight;
}

/**
 * Fades each new page in and pops its first-screen `[data-pop]` blocks;
 * `[data-reveal]` (and off-screen `[data-pop]`) enter on scroll. Wires
 * `[data-magnetic]` and `[data-tilt]`. Blocks that render later (data from the
 * network) get the same treatment once. Everything lives in one gsap.context
 * reverted on unmount.
 */
export default function Template({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  const { reduced, touch, intensity, ready } = useMotion();
  // Lazy state survives StrictMode's double effects and is fixed per mount.
  const [initialLoad] = useState(() => !documentMounted);
  // Path that already played its entry: the entry plays once per page, not
  // again when the motion env changes. Deeper navigations (/reports/a ->
  // /reports/b) reuse this template, so the path is what counts.
  const entered = useRef<string | null>(null);

  // Layout effect: on a client navigation the hidden state is set before the
  // new page is painted, so nothing flashes visible -> hidden.
  useLayoutEffect(() => {
    documentMounted = true;
    const root = ref.current;
    if (!ready || !root) return;

    const documentLoad = initialLoad && entered.current === null;
    const firstEntry = entered.current !== pathname;
    entered.current = pathname;
    // On the document load the SSR content is already painted: no fade, only
    // what CSS pre-hid (html.motion) animates in. The landing's first load has
    // its own choreography, so nothing pops there.
    const fade = firstEntry && !documentLoad;
    const popOnEntry = firstEntry && !(documentLoad && pathname === "/");

    const seen = new WeakSet<Element>();
    const fresh = (selector: string) =>
      gsap.utils.toArray<HTMLElement>(selector, root).filter((el) => {
        if (seen.has(el)) return false;
        seen.add(el);
        return true;
      });

    const cleanups: Array<() => void> = [];
    const frames = new Set<number>();
    let observer: MutationObserver | undefined;
    const revealed = new WeakSet<Element>();
    const pending = new Set<ScrollTrigger>();
    let refreshFrame = 0;
    let sweep = () => {};

    const ctx = gsap.context((self) => {
      const show = (batch: Element[]) => {
        const els = batch.filter((el) => !revealed.has(el));
        if (!els.length) return;
        els.forEach((el) => revealed.add(el));
        self.add(() =>
          gsap.to(els, {
            opacity: 1,
            y: 0,
            duration: REVEAL_DURATION,
            ease: EASE.out,
            stagger: scaled(STAGGER.base, intensity),
            overwrite: true,
          }),
        );
      };

      // Safety net: a reveal whose start sits at (or past) the end of the
      // scroll range may never be crossed (short page, last block of a page),
      // and one clamped to a start the scroll already sits on is never
      // "entered" either (e.g. in view after content above it shrank): both
      // show right away.
      sweep = () => {
        const max = ScrollTrigger.maxScroll(window);
        for (const st of pending) {
          const el = st.trigger;
          if (!el || revealed.has(el) || !el.isConnected) {
            pending.delete(st);
          } else if (st.start >= max - 1 || st.start <= st.scroll()) {
            pending.delete(st);
            show([el]);
          }
        }
      };
      ScrollTrigger.addEventListener("refresh", sweep);

      // One refresh per frame after the DOM changes (late content can move or
      // shrink the page and leave trigger positions stale).
      const scheduleRefresh = () => {
        if (refreshFrame || !pending.size) return;
        refreshFrame = requestAnimationFrame(() => {
          refreshFrame = 0;
          ScrollTrigger.refresh();
        });
      };

      // Animates in a set of [data-pop]/[data-reveal] already set to opacity 0.
      const enter = (els: HTMLElement[], pop: boolean) => {
        const popNow = els.filter((el) => el.matches("[data-pop]") && inFirstScreen(el));
        const reveals = els.filter((el) => !popNow.includes(el));

        if (popNow.length && pop) {
          const stagger = Math.min(
            scaled(STAGGER.pop, intensity),
            popNow.length > 1 ? (POP_TOTAL - DURATION.pop) / (popNow.length - 1) : 0,
          );
          gsap.fromTo(
            popNow,
            { opacity: 0, scale: POP_SCALE },
            {
              opacity: 1,
              scale: 1,
              duration: DURATION.pop,
              ease: EASE.stick,
              stagger,
              clearProps: "scale",
            },
          );
        } else if (popNow.length) {
          gsap.set(popNow, { opacity: 1 });
        }

        if (reveals.length) {
          const offset = scaled(REVEAL_DISTANCE, intensity);
          gsap.set(reveals, { y: offset });
          const triggers = ScrollTrigger.batch(reveals, {
            // ScrollTrigger measures the transformed box, so undo the y
            // pre-offset; clamp so a start past the end of the page is reachable.
            start: `clamp(top-=${offset} 90%)`,
            once: true,
            onEnter: show,
            // Already scrolled past (restored scroll on back/forward): show.
            onLeave: show,
          });
          triggers.forEach((st) => pending.add(st));
          sweep();
          scheduleRefresh();
        }
      };

      const wire = () => {
        if (touch || reduced) return;
        for (const el of fresh("[data-magnetic]")) {
          const strength = Number.parseFloat(el.dataset.magnetic ?? "");
          cleanups.push(attachMagnetic(el, Number.isFinite(strength) ? strength : 0.3));
        }
        for (const el of fresh("[data-tilt]")) {
          cleanups.push(attachTilt(el, el.dataset.tilt === "lift" ? "lift" : "3d"));
        }
      };

      // Hides what is new now (before paint) and measures it next frame, once
      // Next has applied its scroll for this navigation.
      const scan = (pop: boolean) => {
        const els = fresh(ANIMATED);
        wire();
        if (!els.length) return;
        if (reduced) {
          // Only the fade. html.motion is absent so nothing is pre-hidden;
          // force visible in case the preference changed mid-session.
          gsap.set(els, { opacity: 1 });
          return;
        }
        gsap.set(els, { opacity: 0 });
        const frame = requestAnimationFrame(() => {
          frames.delete(frame);
          self.add(() => enter(els, pop));
        });
        frames.add(frame);
      };

      if (fade) {
        gsap.fromTo(
          root,
          { opacity: 0 },
          { opacity: 1, duration: DURATION.fade, ease: "none", clearProps: "opacity" },
        );
      }
      scan(popOnEntry);
      // Blocks that arrive later (after a fetch) enter once, popping if they
      // land in the first screen.
      observer = new MutationObserver((records) => {
        if (records.some((r) => r.addedNodes.length)) self.add(() => scan(true));
        scheduleRefresh();
      });
      observer.observe(root, { childList: true, subtree: true });
    }, root);

    return () => {
      observer?.disconnect();
      ScrollTrigger.removeEventListener("refresh", sweep);
      cancelAnimationFrame(refreshFrame);
      frames.forEach((f) => cancelAnimationFrame(f));
      cleanups.forEach((fn) => fn());
      ctx.revert();
    };
  }, [ready, reduced, touch, intensity, initialLoad, pathname]);

  return (
    <div ref={ref} className="flex flex-1 flex-col">
      {children}
    </div>
  );
}
