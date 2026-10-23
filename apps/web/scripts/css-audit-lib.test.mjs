import { test } from "node:test";
import assert from "node:assert/strict";
import { findPageStylesheets, formatSummary, summarize } from "./css-audit-lib.mjs";

const INPUT =
  "a{color:red}b{color:#f00;z-index:2}.x .y{animation-duration:200ms!important}";

test("summarize cuenta reglas, declaraciones y valores únicos", () => {
  const s = summarize(INPUT);
  assert.equal(s.rules, 3);
  assert.equal(s.declarations, 4);
  assert.equal(s.importants, 1);
  assert.equal(s.unique.zIndexes, 1);
  assert.equal(s.unique.durations, 1);
  assert.equal(s.bytes, Buffer.byteLength(INPUT));
  assert.ok(s.gzipBytes > 0);
});

test("findPageStylesheets devuelve solo hojas de estilo, sin query string", () => {
  const html = `<html><head>
    <link rel="stylesheet" href="/_next/static/chunks/a.css?dpl=x">
    <link rel="preload" href="/c.css">
    <link rel="stylesheet" href="/_next/static/chunks/b.css">
  </head></html>`;
  assert.deepEqual(findPageStylesheets(html), [
    "/_next/static/chunks/a.css",
    "/_next/static/chunks/b.css",
  ]);
});

test("findPageStylesheets sin enlaces devuelve []", () => {
  assert.deepEqual(findPageStylesheets("<html></html>"), []);
});

test("formatSummary incluye el título y el número de reglas", () => {
  const out = formatSummary("Portada (/)", summarize(INPUT));
  assert.ok(out.includes("Portada (/)"));
  assert.ok(out.includes("Reglas: 3"));
});
