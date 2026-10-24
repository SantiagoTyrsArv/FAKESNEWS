"use client";

import { Fragment, useLayoutEffect, useRef } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { gsap } from "@/lib/motion/gsap";

const WORDS = ["VERIFICA", "CONTRASTA", "CITA"];
const REPEAT = 10;
// How far the band travels (share of its length) while it crosses the screen.
const TRAVEL = 15;

// A slightly tilted ink band that slides with the scroll. Decorative only;
// gone with reduced motion.
export function Marquee() {
  const ref = useRef<HTMLDivElement>(null);
  const { reduced, ready } = useMotion();

  useLayoutEffect(() => {
    const el = ref.current;
    const track = el?.querySelector<HTMLElement>("[data-marquee-track]");
    if (!ready || reduced || !el || !track) return;
    const ctx = gsap.context(() => {
      gsap.fromTo(
        track,
        { xPercent: 0 },
        {
          xPercent: -TRAVEL,
          ease: "none",
          scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: true },
        },
      );
    }, el);
    return () => ctx.revert();
  }, [ready, reduced]);

  return (
    <div ref={ref} aria-hidden="true" className="overflow-x-clip py-6 motion-reduce:hidden">
      <div className="-mx-8 -rotate-[1.5deg] bg-ink py-3 text-paper sm:py-4">
        <div
          data-marquee-track
          className="flex w-max font-heading text-2xl font-semibold tracking-wide whitespace-nowrap sm:text-4xl"
        >
          {Array.from({ length: REPEAT }, (_, i) => (
            <span key={i} className="flex shrink-0">
              {WORDS.map((word) => (
                <Fragment key={word}>
                  <span className="px-4">{word}</span>
                  <span className="text-collage-orange">✶</span>
                </Fragment>
              ))}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
