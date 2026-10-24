import assert from "node:assert/strict";
import { test } from "node:test";
import { evidenceUrl, sourceUrl } from "./source-url.mjs";

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

test("evidenceUrl: http(s) links pass through unchanged", () => {
  for (const ok of ["https://reuters.com/a?b=1", "http://cdc.gov/x", "HTTPS://bbc.co.uk/"]) {
    assert.equal(evidenceUrl(ok), ok, ok);
  }
});

test("evidenceUrl: any other scheme (or no URL) gets no link", () => {
  for (const bad of ["", "javascript:alert(1)", "javascript://reuters.com/%0Aalert(1)", " data:text/html,x", "vbscript:x", "/relative", "reuters.com"]) {
    assert.equal(evidenceUrl(bad), null, bad);
  }
});
