import { gsap } from "@/lib/motion/gsap";
import { DURATION, EASE } from "@/lib/motion/tokens.mjs";

const RELEASE_DURATION = 0.8;
const TILT_DEG = 10;
const LIFT_PX = 4;

/**
 * Makes `el` follow the cursor by `strength` (0..1) times the pointer's offset
 * from its center, and spring back with `EASE.release` when the pointer leaves.
 * Returns the cleanup function.
 */
export function attachMagnetic(el: HTMLElement, strength: number): () => void {
  const s = Math.min(Math.max(strength, 0), 1);
  const xTo = gsap.quickTo(el, "x", { duration: DURATION.hover, ease: EASE.out });
  const yTo = gsap.quickTo(el, "y", { duration: DURATION.hover, ease: EASE.out });

  const onMove = (e: PointerEvent) => {
    if (e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    xTo((e.clientX - (r.left + r.width / 2)) * s);
    yTo((e.clientY - (r.top + r.height / 2)) * s);
  };
  const onLeave = () => {
    gsap.to(el, {
      x: 0,
      y: 0,
      duration: RELEASE_DURATION,
      ease: EASE.release,
      overwrite: true,
    });
  };

  el.addEventListener("pointermove", onMove);
  el.addEventListener("pointerleave", onLeave);
  return () => {
    el.removeEventListener("pointermove", onMove);
    el.removeEventListener("pointerleave", onLeave);
    gsap.killTweensOf(el);
    gsap.set(el, { clearProps: "x,y" });
  };
}

/** `.cutout` descendants: their tilt comes from `--cutout-rotate`. */
function innerCutouts(el: HTMLElement) {
  return [...el.querySelectorAll<HTMLElement>(".cutout")]
    .map((node) => ({
      node,
      rotate: getComputedStyle(node).getPropertyValue("--cutout-rotate").trim(),
    }))
    .filter((t) => t.rotate !== "");
}

/**
 * `"3d"`: rotates `el` up to ±10° on X/Y towards the cursor; `"lift"`: raises it
 * 4 px. Both straighten the cutout tilt (`--cutout-rotate`) to 0 while hovered
 * and restore it on leave. Returns the cleanup function.
 */
export function attachTilt(el: HTMLElement, mode: "3d" | "lift"): () => void {
  const cutouts = innerCutouts(el);
  const nodes = cutouts.map((c) => c.node);
  const hover = { duration: DURATION.hover, ease: EASE.out, overwrite: "auto" as const };
  // Once GSAP transforms `el` it folds the CSS `rotate` (the cutout tilt from
  // --cutout-rotate) into its own `rotation`, so `el` straightens through
  // `rotation`; inner cutouts keep their CSS and straighten through the var.
  let baseRotation: number | null = null;

  const onEnter = (e: PointerEvent) => {
    if (e.pointerType !== "mouse") return;
    if (baseRotation === null) baseRotation = Number(gsap.getProperty(el, "rotation")) || 0;
    if (nodes.length) gsap.to(nodes, { "--cutout-rotate": "0deg", ...hover });
    gsap.to(el, { rotation: 0, ...(mode === "lift" ? { y: -LIFT_PX } : {}), ...hover });
  };
  const onMove = (e: PointerEvent) => {
    if (mode !== "3d" || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    gsap.to(el, {
      rotationY: px * 2 * TILT_DEG,
      rotationX: -py * 2 * TILT_DEG,
      transformPerspective: 800,
      ...hover,
    });
  };
  const onLeave = () => {
    if (nodes.length) {
      gsap.to(nodes, { "--cutout-rotate": (i: number) => cutouts[i].rotate, ...hover });
    }
    gsap.to(el, {
      rotation: baseRotation ?? 0,
      ...(mode === "3d" ? { rotationX: 0, rotationY: 0 } : { y: 0 }),
      ...hover,
    });
  };

  el.addEventListener("pointerenter", onEnter);
  el.addEventListener("pointermove", onMove);
  el.addEventListener("pointerleave", onLeave);
  return () => {
    el.removeEventListener("pointerenter", onEnter);
    el.removeEventListener("pointermove", onMove);
    el.removeEventListener("pointerleave", onLeave);
    gsap.killTweensOf([el, ...nodes]);
    // Hands the transform back to CSS (including the cutout `rotate`).
    if (baseRotation !== null) gsap.set(el, { clearProps: "transform" });
    nodes.forEach((n) => n.style.removeProperty("--cutout-rotate"));
  };
}
