"use client";

import { useEffect, useRef } from "react";
import { gsap } from "@/lib/motion/gsap";

const HOVER = 'a, button, [role="button"], [data-tilt]';
const TEXT = "input, textarea, select, [contenteditable]";
const BASE = 38;
const BIG = 84;
const MID = 56;

export function Cursor({ label }: Readonly<{ label: boolean }>) {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const scaleRef = useRef<HTMLDivElement>(null);
  const blueRef = useRef<HTMLDivElement>(null);
  const fillRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  const labelRef = useRef(label);
  const refreshRef = useRef<() => void>(() => {});

  useEffect(() => {
    labelRef.current = label;
    // Re-apply the current hover state so a route change that flips the label
    // (intensity) restyles the ring even if the pointer is still over a link.
    refreshRef.current();
  }, [label]);

  useEffect(() => {
    if (!window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const dot = dotRef.current;
    const ring = ringRef.current;
    const scaler = scaleRef.current;
    const blue = blueRef.current;
    const fill = fillRef.current;
    const text = textRef.current;
    const root = document.documentElement;
    if (!dot || !ring || !scaler || !blue || !fill || !text) return;

    gsap.set([dot, ring], { xPercent: -50, yPercent: -50, x: -100, y: -100 });
    gsap.set(scaler, { scale: BASE / BIG });
    gsap.set(dot, { scale: 1 });
    gsap.set([fill, blue, text], { opacity: 0 });
    gsap.set([dot, ring], { autoAlpha: 0 });

    const dx = gsap.quickTo(dot, "x", { duration: 0.01 });
    const dy = gsap.quickTo(dot, "y", { duration: 0.01 });
    const rx = gsap.quickTo(ring, "x", { duration: 0.45, ease: "expo.out" });
    const ry = gsap.quickTo(ring, "y", { duration: 0.45, ease: "expo.out" });

    let visible = false;
    let state: "idle" | "hover" | "text" = "idle";

    const show = (on: boolean) => {
      if (on === visible) return;
      visible = on;
      root.classList.toggle("cursor-on", on);
      gsap.to([dot, ring], { autoAlpha: on ? 1 : 0, duration: 0.2, overwrite: "auto" });
    };

    const apply = (next: typeof state) => {
      if (next === state) return;
      state = next;
      if (next === "text") {
        show(false);
        return;
      }
      const hover = next === "hover";
      const label = labelRef.current;
      const big = hover && label;
      gsap.to(scaler, {
        scale: hover ? (label ? BIG : MID) / BIG : BASE / BIG,
        duration: 0.45,
        ease: "expo.out",
        overwrite: "auto",
      });
      gsap.to(fill, { opacity: big ? 1 : 0, duration: 0.3, overwrite: "auto" });
      gsap.to(blue, { opacity: hover ? 1 : 0, duration: 0.3, overwrite: "auto" });
      gsap.to(text, { opacity: big ? 1 : 0, duration: 0.25, overwrite: "auto" });
      gsap.to(dot, { scale: hover ? 0 : 1, duration: 0.25, overwrite: "auto" });
    };

    refreshRef.current = () => {
      const current = state;
      if (current === "text") return;
      state = "idle";
      apply(current);
    };

    const classify = (t: EventTarget | null): typeof state => {
      const el = t instanceof Element ? t : null;
      if (!el) return "idle";
      if (el.closest(TEXT)) return "text";
      if (el.closest(HOVER)) return "hover";
      return "idle";
    };

    const onMove = (e: PointerEvent) => {
      if (e.pointerType && e.pointerType !== "mouse") return;
      dx(e.clientX);
      dy(e.clientY);
      rx(e.clientX);
      ry(e.clientY);
      const next = classify(e.target);
      if (!visible && next !== "text") {
        // Jump the ring to the pointer on first appearance.
        gsap.set(ring, { x: e.clientX, y: e.clientY });
        gsap.set(dot, { x: e.clientX, y: e.clientY });
        show(true);
      }
      if (next === "text") show(false);
      else if (state === "text") {
        state = "idle";
        show(true);
      }
      apply(next);
    };
    const onLeave = () => show(false);
    const onEnter = () => {
      if (state !== "text") show(true);
    };

    document.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("mouseleave", onLeave);
    document.documentElement.addEventListener("mouseenter", onEnter);
    window.addEventListener("blur", onLeave);

    return () => {
      document.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("mouseleave", onLeave);
      document.documentElement.removeEventListener("mouseenter", onEnter);
      window.removeEventListener("blur", onLeave);
      refreshRef.current = () => {};
      root.classList.remove("cursor-on");
      gsap.killTweensOf([dot, ring, scaler, blue, fill, text]);
    };
  }, []);

  return (
    <div aria-hidden="true" className="cursor-root">
      <div ref={ringRef} className="cursor-ring">
        <div ref={scaleRef} className="cursor-scale">
          <div ref={fillRef} className="cursor-fill" />
          <div ref={blueRef} className="cursor-blue" />
        </div>
        <span ref={textRef} className="cursor-label">
          {label ? "Ver" : ""}
        </span>
      </div>
      <div ref={dotRef} className="cursor-dot" />
    </div>
  );
}
