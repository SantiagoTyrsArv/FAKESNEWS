/** Shared motion tokens. Durations are in seconds. */

export const EASE = {
  out: "expo.out",
  stick: "back.out(1.4)",
  release: "elastic.out(1, 0.4)",
  css: "cubic-bezier(0.16, 1, 0.3, 1)",
};

export const DURATION = { enter: 0.9, hover: 0.35, pop: 0.25, fade: 0.2 };

export const STAGGER = { base: 0.09, pop: 0.04 };

/**
 * Motion intensity for a route: full on the landing, softened elsewhere.
 * @param {string} pathname
 * @returns {1 | 0.75}
 */
export function intensityFor(pathname) {
  return pathname === "/" ? 1 : 0.75;
}

/**
 * @param {number} value
 * @param {number} intensity
 * @returns {number}
 */
export function scaled(value, intensity) {
  return value * intensity;
}
