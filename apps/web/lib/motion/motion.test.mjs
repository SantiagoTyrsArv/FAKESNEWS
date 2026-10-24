import assert from "node:assert/strict";
import { test } from "node:test";
import { DURATION, EASE, STAGGER, intensityFor, scaled } from "./tokens.mjs";
import { getMotionEnv, onceInSession } from "./env.mjs";

test("intensityFor: 1 only on the landing", () => {
  assert.equal(intensityFor("/"), 1);
  assert.equal(intensityFor("/history"), 0.75);
  assert.equal(intensityFor("/reports/abc"), 0.75);
  assert.equal(intensityFor("/login"), 0.75);
});

test("scaled multiplies by intensity", () => {
  assert.equal(scaled(80, 0.75), 60);
  assert.equal(scaled(80, 1), 80);
});

test("tokens keep the agreed values", () => {
  assert.equal(EASE.out, "expo.out");
  assert.equal(EASE.css, "cubic-bezier(0.16, 1, 0.3, 1)");
  assert.equal(DURATION.enter, 0.9);
  assert.equal(STAGGER.pop, 0.04);
});

test("getMotionEnv reads reduced-motion and touch queries", () => {
  assert.deepEqual(getMotionEnv((q) => ({ matches: q.includes("reduce") })), {
    reduced: true,
    touch: false,
  });
  assert.deepEqual(
    getMotionEnv((q) => ({ matches: q.includes("hover: none") })),
    { reduced: false, touch: true },
  );
  assert.equal(
    getMotionEnv((q) => ({ matches: q.includes("pointer: coarse") })).touch,
    true,
  );
});

test("onceInSession is true once, then false", () => {
  const data = new Map();
  const storage = {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
  };
  assert.equal(onceInSession("curtain", () => storage), true);
  assert.equal(onceInSession("curtain", () => storage), false);
  assert.equal(onceInSession("other", () => storage), true);
});

test("onceInSession is false (no throw) when storage throws", () => {
  const getThrows = {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {},
  };
  const setThrows = {
    getItem: () => null,
    setItem: () => {
      throw new Error("quota");
    },
  };
  assert.equal(onceInSession("k", () => getThrows), false);
  assert.equal(onceInSession("k", () => setThrows), false);
});

test("onceInSession is false (no throw) when reading the storage itself throws", () => {
  const blocked = () => {
    throw new Error("SecurityError");
  };
  assert.equal(onceInSession("k", blocked), false);
});
