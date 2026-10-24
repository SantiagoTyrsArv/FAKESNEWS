import assert from "node:assert/strict";
import { test } from "node:test";
import { buildCsp } from "./csp.mjs";

const directives = (csp) =>
  Object.fromEntries(
    csp.split(";").map((d) => d.trim()).filter(Boolean).map((d) => {
      const [name, ...values] = d.split(/\s+/);
      return [name, values];
    }),
  );

test("buildCsp: production locks down framing, plugins, base and forms", () => {
  const d = directives(buildCsp({ dev: false, apiUrl: "/api" }));
  assert.deepEqual(d["default-src"], ["'self'"]);
  assert.deepEqual(d["frame-ancestors"], ["'none'"]);
  assert.deepEqual(d["object-src"], ["'none'"]);
  assert.deepEqual(d["base-uri"], ["'self'"]);
  assert.deepEqual(d["form-action"], ["'self'"]);
  assert.ok("upgrade-insecure-requests" in d);
  assert.ok(!d["script-src"].includes("'unsafe-eval'"));
});

test("buildCsp: a same-origin API (/api) only needs 'self'", () => {
  const d = directives(buildCsp({ dev: false, apiUrl: "/api" }));
  assert.deepEqual(d["connect-src"], ["'self'"]);
});

test("buildCsp: an absolute API URL is allowed by origin, not path", () => {
  const d = directives(buildCsp({ dev: false, apiUrl: "https://api.example.com/v1" }));
  assert.deepEqual(d["connect-src"], ["'self'", "https://api.example.com"]);
});

test("buildCsp: development allows eval for hot reload and stays on http", () => {
  const d = directives(buildCsp({ dev: true, apiUrl: "http://localhost:8000" }));
  assert.ok(d["script-src"].includes("'unsafe-eval'"));
  assert.ok(!("upgrade-insecure-requests" in d));
  assert.deepEqual(d["connect-src"], ["'self'", "http://localhost:8000"]);
});

test("buildCsp: a plain-http API (local production build) isn't upgraded to https", () => {
  const d = directives(buildCsp({ dev: false, apiUrl: "http://localhost:8000" }));
  assert.ok(!("upgrade-insecure-requests" in d));
  assert.deepEqual(d["connect-src"], ["'self'", "http://localhost:8000"]);
});
