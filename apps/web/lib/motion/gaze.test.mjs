import assert from "node:assert/strict";
import { test } from "node:test";
import { lensTilt, pupilOffset } from "./gaze.mjs";

const close = (actual, expected) => {
  assert.ok(Math.abs(actual.x - expected.x) < 1e-9, `x: ${actual.x} != ${expected.x}`);
  assert.ok(Math.abs(actual.y - expected.y) < 1e-9, `y: ${actual.y} != ${expected.y}`);
};

test("pupilOffset: no vector, no offset", () => {
  assert.deepEqual(pupilOffset(0, 0, 5), { x: 0, y: 0 });
});

test("pupilOffset: far away caps at max", () => {
  close(pupilOffset(600, 0, 5), { x: 5, y: 0 });
});

test("pupilOffset: close by scales with distance / 60", () => {
  close(pupilOffset(30, 0, 5), { x: 2.5, y: 0 });
});

test("pupilOffset: keeps the vector's direction", () => {
  close(pupilOffset(-300, -400, 5), { x: -3, y: -4 });
});

test("lensTilt: straight ahead is 0", () => {
  assert.equal(lensTilt(0, 30), 0);
});

test("lensTilt: scales with dx / 240", () => {
  assert.equal(lensTilt(120, 30), 15);
});

test("lensTilt: caps at ±max", () => {
  assert.equal(lensTilt(-1000, 30), -30);
  assert.equal(lensTilt(1000, 30), 30);
});
