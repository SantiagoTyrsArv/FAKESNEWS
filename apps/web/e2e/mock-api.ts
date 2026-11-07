import type { BrowserContext, Page, Route } from "@playwright/test";

const API = "http://localhost:8000";
export const CASE_ID = "00000000-0000-4000-8000-000000000001";

export const VERDICT_LABEL = "Respaldada por fuentes";

function submission(id: string, rawInput: string, status: string) {
  return {
    id,
    input_type: "text",
    raw_input: rawInput,
    status,
    error: null,
    // Recent, or the report page takes the case for a stalled one.
    created_at: new Date().toISOString(),
  };
}

function evidence(url: string, published_at: string | null, stance: string) {
  return {
    url: `https://www.eltiempo.com/${url}`,
    snippet: "Una cita de la noticia.",
    published_at,
    stance,
    source: {
      domain: "eltiempo.com",
      name: "El Tiempo",
      type: "media",
      score: 0.8,
      cases_count: 20,
      low_sample: false,
    },
  };
}

// What the API sends today, with no `changed` in the summary, plus a claim
// whose sources come out of order.
export function changedReport() {
  const shared = { confidence_note: null, verification_failed: false };
  return {
    submission: submission(CASE_ID, "La inflación cayó del 13 % al 5 %.", "done"),
    summary: { total_claims: 2, supported: 1, contradicted: 0, insufficient: 0, failed: 0 },
    disclaimer: "Este reporte resume lo que dicen las fuentes.",
    claims: [
      {
        ...shared,
        id: "00000000-0000-4000-8000-000000000003",
        text: "La inflación cayó del 13 % al 5 %.",
        verdict: "CHANGED",
        rationale: "Bajó, pero después volvió a subir.",
        evidence: [
          evidence("reciente", "2026-01-30", "contradicts"),
          evidence("sin-fecha", "hace 2 días", "neutral"),
          evidence("antigua", "2022-12-15", "supports"),
        ],
      },
      {
        ...shared,
        id: "00000000-0000-4000-8000-000000000004",
        text: "Otra afirmación.",
        verdict: "SUPPORTED",
        rationale: "Las fuentes lo confirman.",
        evidence: [evidence("otra", "2026-01-01", "supports")],
      },
    ],
  };
}

function report(rawInput: string) {
  const case_ = submission(CASE_ID, rawInput, "done");
  return {
    submission: case_,
    summary: {
      total_claims: 1,
      supported: 1,
      contradicted: 0,
      insufficient: 0,
      failed: 0,
    },
    disclaimer: "Este reporte resume lo que dicen las fuentes.",
    claims: [
      {
        id: "00000000-0000-4000-8000-000000000002",
        text: rawInput,
        verdict: "SUPPORTED",
        rationale: "Las fuentes lo confirman.",
        confidence_note: null,
        verification_failed: false,
        evidence: [
          {
            url: "https://www.eltiempo.com/noticia",
            snippet: "Una cita de la noticia.",
            published_at: "2026-11-01",
            stance: "supports",
            source: {
              domain: "eltiempo.com",
              name: "El Tiempo",
              type: "media",
              score: 0.8,
              cases_count: 20,
              low_sample: false,
            },
          },
        ],
      },
    ],
  };
}

// Stands in for the API in the browser. Requests from the page go straight to
// it, so this needs no server, no quota and no third party.
export async function mockApi(
  page: Page,
  context: BrowserContext,
  caseReport?: ReturnType<typeof changedReport>,
) {
  let rawInput = "";
  let polls = 0;
  const user = { id: "u", email: "e2e@example.com", mfa_enabled: true };

  async function handle(route: Route) {
    const { pathname, searchParams } = new URL(route.request().url());
    const method = route.request().method();
    const json = (body: unknown, status = 200) => route.fulfill({ status, json: body });

    if (method === "POST" && pathname === "/auth/register") return json(user, 201);
    if (method === "POST" && pathname === "/auth/login") {
      // The API sets this one: without it the web sends /history to /login.
      await context.addCookies([
        { name: "access_token", value: "e2e", domain: "localhost", path: "/" },
      ]);
      return json({ status: "authenticated", user });
    }
    if (pathname === "/auth/me") return json(user);
    if (method === "POST" && pathname === "/submissions") {
      rawInput = route.request().postDataJSON().raw_input;
      return json(submission(CASE_ID, rawInput, "queued"), 201);
    }
    if (pathname === `/submissions/${CASE_ID}`) {
      polls += 1;
      return json(submission(CASE_ID, rawInput, polls > 1 ? "done" : "verifying"));
    }
    if (pathname === `/reports/${CASE_ID}`) return json(caseReport ?? report(rawInput));
    if (pathname === "/submissions") {
      return searchParams.has("cursor")
        ? json({ submissions: [submission("older", "Un caso anterior", "done")], next_cursor: null })
        : json({ submissions: [submission(CASE_ID, rawInput, "done")], next_cursor: "page-2" });
    }
    return json({ detail: `Sin simular: ${method} ${pathname}` }, 404);
  }

  await page.route(`${API}/**`, handle);
}
