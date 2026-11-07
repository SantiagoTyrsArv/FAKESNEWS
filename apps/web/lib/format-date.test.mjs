import assert from "node:assert/strict";
import { test } from "node:test";
import { formatPublishedDate } from "./format-date.mjs";

test("formatPublishedDate: a search engine date reads in Spanish", () => {
  assert.equal(formatPublishedDate("Wed, 04 Nov 2026 14:33:05 GMT"), "4 de noviembre de 2026");
});

test("formatPublishedDate: the day doesn't shift with the time zone", () => {
  assert.equal(formatPublishedDate("Tue, 03 Nov 2026 23:58:05 GMT"), "3 de noviembre de 2026");
});

test("formatPublishedDate: an ISO date works too", () => {
  assert.equal(formatPublishedDate("2026-11-05"), "5 de noviembre de 2026");
});

test("formatPublishedDate: text that isn't a date stays as it is", () => {
  assert.equal(formatPublishedDate("hace 2 días"), "hace 2 días");
});
