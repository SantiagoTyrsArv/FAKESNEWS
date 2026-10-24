// Pupils move toward a target but saturate within GAZE_RANGE px of the eye, so
// a cursor next to a character looks at it and one far away just pins the
// pupil to the edge.
const GAZE_RANGE = 60;

/**
 * Pupil offset for an eye looking along (dx, dy): same direction, magnitude
 * `max × min(dist / 60, 1)`.
 * @param {number} dx
 * @param {number} dy
 * @param {number} max
 * @returns {{ x: number, y: number }}
 */
export function pupilOffset(dx, dy, max) {
  const dist = Math.hypot(dx, dy);
  if (dist === 0) return { x: 0, y: 0 };
  const k = (max * Math.min(dist / GAZE_RANGE, 1)) / dist;
  return { x: dx * k, y: dy * k };
}

// The detective's magnifier tilts toward the cursor, fully once the cursor is
// LENS_RANGE px to either side.
const LENS_RANGE = 240;

/**
 * Magnifier tilt in degrees for a target `dx` px to the side: `max × clamp(dx
 * / 240, -1, 1)`.
 * @param {number} dx
 * @param {number} max
 * @returns {number}
 */
export function lensTilt(dx, max) {
  return max * Math.min(Math.max(dx / LENS_RANGE, -1), 1);
}
