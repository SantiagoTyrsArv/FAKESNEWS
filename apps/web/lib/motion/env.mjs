/**
 * @param {(query: string) => { matches: boolean }} matchMedia
 * @returns {{ reduced: boolean, touch: boolean }}
 */
export function getMotionEnv(matchMedia) {
  return {
    reduced: matchMedia("(prefers-reduced-motion: reduce)").matches,
    touch:
      matchMedia("(hover: none)").matches ||
      matchMedia("(pointer: coarse)").matches,
  };
}

/**
 * True the first time `key` is seen in this storage (and records it); false
 * afterwards, or when the storage is unavailable (blocked, private mode).
 * @param {string} key
 * @param {Pick<Storage, "getItem" | "setItem">} storage
 * @returns {boolean}
 */
export function onceInSession(key, storage) {
  try {
    if (storage.getItem(key) !== null) return false;
    storage.setItem(key, "1");
    return true;
  } catch {
    return false;
  }
}
