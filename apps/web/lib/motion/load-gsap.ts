import type { gsap as GsapValue } from "gsap";
import type { ScrollTrigger as ScrollTriggerValue } from "gsap/ScrollTrigger";
import type { SplitText as SplitTextValue } from "gsap/SplitText";

export interface GsapBundle {
  gsap: typeof GsapValue;
  ScrollTrigger: typeof ScrollTriggerValue;
  SplitText: typeof SplitTextValue;
}

// Lazy counterpart of lib/motion/gsap.ts: GSAP with both plugins, loaded the
// first time a page actually animates, so it stays out of the first-load
// bundle. The auth characters keep the static module (the login must not
// change); everything else goes through this loader.
let bundle: Promise<GsapBundle> | null = null;

export function loadGsap(): Promise<GsapBundle> {
  bundle ??= Promise.all([
    import("gsap"),
    import("gsap/ScrollTrigger"),
    import("gsap/SplitText"),
    // SplitText measures lines with the font on screen. Split before the web
    // font arrives and the lines break where the fallback font broke them.
    // next/font preloads them, so this rarely waits.
    document.fonts?.ready,
  ]).then(([core, scrollTriggerModule, splitTextModule]) => {
    const { gsap } = core;
    const { ScrollTrigger } = scrollTriggerModule;
    const { SplitText } = splitTextModule;
    gsap.registerPlugin(ScrollTrigger, SplitText);
    return { gsap, ScrollTrigger, SplitText };
  });
  return bundle;
}
