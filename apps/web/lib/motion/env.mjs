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
 * True the first time `key` is seen in the storage (and records it); false
 * afterwards, or when the storage is unavailable. The storage comes from a
 * getter because merely reading the `sessionStorage` global throws when site
 * data is blocked, so that read has to happen inside the guard.
 * @param {string} key
 * @param {() => Pick<Storage, "getItem" | "setItem">} getStorage
 * @returns {boolean}
 */
export function onceInSession(key, getStorage) {
  try {
    const storage = getStorage();
    if (storage.getItem(key) !== null) return false;
    storage.setItem(key, "1");
    return true;
  } catch {
    return false;
  }
}
