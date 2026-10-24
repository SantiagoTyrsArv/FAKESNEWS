import assert from "node:assert/strict";
import { test } from "node:test";
import { sourceUrl } from "./source-url.mjs";

test("sourceUrl: a domain becomes its https home page", () => {
  assert.equal(sourceUrl("cdc.gov"), "https://cdc.gov");
});

test("sourceUrl: subdomains and hyphens are fine", () => {
  assert.equal(sourceUrl("www.who-int.example.org"), "https://www.who-int.example.org");
});

test("sourceUrl: anything that isn't a bare domain gets no link", () => {
  for (const bad of ["", "javascript:alert(1)", "cdc.gov/path", "evil.com@cdc.gov", "cdc gov", "localhost", "-cdc.gov"]) {
    assert.equal(sourceUrl(bad), null, bad);
  }
});
