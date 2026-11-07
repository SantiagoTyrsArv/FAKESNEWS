import assert from "node:assert/strict";
import { test } from "node:test";
import { orderEvidence } from "./evidence-timeline.mjs";

const item = (url, published_at) => ({ url, published_at });

test("orderEvidence: oldest first across date formats", () => {
  const { dated } = orderEvidence([
    item("b", "Wed, 04 Nov 2026 14:33:05 GMT"),
    item("a", "2022-07-01"),
  ]);
  assert.deepEqual(dated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: null and non-dates go to undated, in their order", () => {
  const { dated, undated } = orderEvidence([item("a", null), item("b", "hace 2 días")]);
  assert.deepEqual(dated, []);
  assert.deepEqual(undated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: the same date keeps every item, in the order received", () => {
  const { dated } = orderEvidence([item("a", "2026-01-01"), item("b", "2026-01-01")]);
  assert.deepEqual(dated.map((e) => e.url), ["a", "b"]);
});

test("orderEvidence: the input is not changed", () => {
  const input = [item("b", "2026-01-01"), item("a", "2020-01-01")];
  orderEvidence(input);
  assert.deepEqual(input.map((e) => e.url), ["b", "a"]);
});
