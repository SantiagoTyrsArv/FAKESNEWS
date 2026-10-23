"use client";

import Lenis from "lenis";
import { usePathname } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { gsap, ScrollTrigger } from "@/lib/motion/gsap";
import { getMotionEnv } from "@/lib/motion/env.mjs";
import { intensityFor } from "@/lib/motion/tokens.mjs";

type MotionState = {
  reduced: boolean;
  touch: boolean;
  intensity: 1 | 0.75;
  ready: boolean;
};

const MotionContext = createContext<MotionState>({
  reduced: false,
  touch: false,
  intensity: 0.75,
  ready: false,
});

export function useMotion(): MotionState {
  return useContext(MotionContext);
}

const NO_LENIS_ROUTES = ["/login", "/register"];

const QUERIES = [
  "(prefers-reduced-motion: reduce)",
  "(hover: none)",
  "(pointer: coarse)",
];

function subscribe(onChange: () => void) {
  const lists = QUERIES.map((q) => window.matchMedia(q));
  lists.forEach((m) => m.addEventListener("change", onChange));
  return () => lists.forEach((m) => m.removeEventListener("change", onChange));
}

// A primitive snapshot keeps useSyncExternalStore referentially stable.
function getSnapshot() {
  const { reduced, touch } = getMotionEnv((q) => window.matchMedia(q));
  return `${reduced ? 1 : 0}${touch ? 1 : 0}`;
}

const noopSubscribe = () => () => {};

export function MotionProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const snapshot = useSyncExternalStore(subscribe, getSnapshot, () => "00");
  const ready = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  const reduced = snapshot[0] === "1";
  const touch = snapshot[1] === "1";

  const lenisAllowed =
    ready &&
    !touch &&
    !reduced &&
    !NO_LENIS_ROUTES.some((r) => pathname === r || pathname.startsWith(`${r}/`));

  useEffect(() => {
    if (!lenisAllowed) return;
    const lenis = new Lenis();
    const onScroll = () => ScrollTrigger.update();
    lenis.on("scroll", onScroll);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);
    return () => {
      gsap.ticker.remove(tick);
      lenis.off("scroll", onScroll);
      lenis.destroy();
    };
  }, [lenisAllowed]);

  const value = useMemo<MotionState>(
    () => ({ reduced, touch, intensity: intensityFor(pathname), ready }),
    [reduced, touch, pathname, ready],
  );

  return <MotionContext.Provider value={value}>{children}</MotionContext.Provider>;
}
