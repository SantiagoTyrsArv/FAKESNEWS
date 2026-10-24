"use client";

import { useLayoutEffect, useRef, type ReactNode } from "react";
import { useMotion } from "@/components/motion/motion-provider";
import { type HeaderVariant, SiteHeader } from "@/components/site-header";
import { gsap, SplitText } from "@/lib/motion/gsap";
import { DURATION, EASE, STAGGER, scaled } from "@/lib/motion/tokens.mjs";
import { cn } from "@/lib/utils";

const LINE_ROTATE = 4;

export function AppShell({
  children,
  variant = "app",
  width = "default",
}: {
  children: ReactNode;
  variant?: HeaderVariant;
  width?: "default" | "narrow";
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader variant={variant} />
      <main
        className={cn(
          "mx-auto flex w-full flex-1 flex-col gap-8 px-4 py-8 sm:px-6 sm:py-12",
          width === "narrow" ? "max-w-2xl" : "max-w-5xl",
        )}
      >
        {children}
      </main>
    </div>
  );
}

export function PageHeading({
  title,
  description,
  actions,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  const ref = useRef<HTMLHeadingElement>(null);
  const { reduced, touch, intensity, ready } = useMotion();

  // Desktop only: the title rises line by line from a mask. It is never hidden
  // by opacity, only by the mask on text that is already painted, and the split
  // is undone when the reveal ends so the heading goes back to plain markup.
  useLayoutEffect(() => {
    const h1 = ref.current;
    if (!ready || reduced || touch || !h1) return;
    const split = SplitText.create(h1, { type: "lines", mask: "lines" });
    const tween = gsap.fromTo(
      split.lines,
      { yPercent: 110, rotation: scaled(LINE_ROTATE, intensity) },
      {
        yPercent: 0,
        rotation: 0,
        transformOrigin: "0% 100%",
        duration: DURATION.enter,
        ease: EASE.out,
        stagger: scaled(STAGGER.base, intensity),
        onComplete: () => split.revert(),
      },
    );
    return () => {
      tween.kill();
      split.revert();
    };
  }, [ready, reduced, touch, intensity]);

  return (
    <div data-pop className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex max-w-2xl flex-col gap-2">
        <h1 ref={ref} className="font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
          {title}
        </h1>
        {description && (
          <p className="text-[0.95rem] leading-relaxed text-pretty text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 gap-2">{actions}</div>}
    </div>
  );
}

export function LoadingLine({ children = "Cargando…" }: { children?: ReactNode }) {
  return (
    <p className="animate-pulse text-sm text-muted-foreground" role="status">
      {children}
    </p>
  );
}
