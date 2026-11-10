import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import type { Report, Submission } from "@/lib/cases";
import { ServerApiError, loadInitialCase, serverApiBase, serverFetch } from "@/lib/server-api";

const API = "http://localhost:8000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("serverApiBase", () => {
  it("prefers API_PROXY_TARGET without trailing slashes", () => {
    expect(
      serverApiBase({
        API_PROXY_TARGET: "https://api.example.com//",
        NEXT_PUBLIC_API_URL: "https://other.example.com",
      }),
    ).toBe("https://api.example.com");
  });

  it("uses NEXT_PUBLIC_API_URL when it is absolute", () => {
    expect(serverApiBase({ NEXT_PUBLIC_API_URL: "http://api.local:8000/" })).toBe(
      "http://api.local:8000",
    );
  });

  it("ignores a relative NEXT_PUBLIC_API_URL such as /api", () => {
    expect(serverApiBase({ NEXT_PUBLIC_API_URL: "/api" })).toBe("http://localhost:8000");
  });

  it("falls back to the local API", () => {
    expect(serverApiBase({})).toBe("http://localhost:8000");
  });
});

describe("serverFetch", () => {
  it("returns the JSON body on 200", async () => {
    server.use(http.get(`${API}/sources`, () => HttpResponse.json({ sources: [] })));

    await expect(serverFetch("/sources")).resolves.toEqual({ sources: [] });
  });

  it("throws ServerApiError with the status when the response is not OK", async () => {
    server.use(http.get(`${API}/sources`, () => new HttpResponse(null, { status: 503 })));

    const error = await serverFetch("/sources").catch((err: unknown) => err);
    expect(error).toBeInstanceOf(ServerApiError);
    expect((error as ServerApiError).status).toBe(503);
  });

  it("throws ServerApiError when the network fails", async () => {
    server.use(http.get(`${API}/sources`, () => HttpResponse.error()));

    await expect(serverFetch("/sources")).rejects.toBeInstanceOf(ServerApiError);
  });
});

describe("loadInitialCase", () => {
  const ID = "1b4e28ba-2fa1-11d2-883f-0016d3cca427";

  function submission(status: Submission["status"]): Submission {
    return {
      id: ID,
      input_type: "text",
      raw_input: "texto",
      status,
      error: null,
      created_at: "2026-11-09T10:00:00Z",
    };
  }

  it("returns null without a token and makes no request", async () => {
    let requests = 0;
    server.use(
      http.all(`${API}/*`, () => {
        requests += 1;
        return HttpResponse.json(submission("verifying"));
      }),
    );

    await expect(loadInitialCase(ID, undefined)).resolves.toBeNull();
    expect(requests).toBe(0);
  });

  it("sends only the access_token cookie", async () => {
    const seen: (string | null)[] = [];
    server.use(
      http.get(`${API}/submissions/${ID}`, ({ request }) => {
        seen.push(request.headers.get("cookie"));
        return HttpResponse.json(submission("verifying"));
      }),
    );

    await loadInitialCase(ID, "abc");

    expect(seen).toEqual(["access_token=abc"]);
  });

  it("returns the submission without a report while the case is in progress", async () => {
    server.use(
      http.get(`${API}/submissions/${ID}`, () => HttpResponse.json(submission("verifying"))),
    );

    await expect(loadInitialCase(ID, "abc")).resolves.toEqual({
      submission: submission("verifying"),
      report: null,
    });
  });

  it("also fetches the report when the case is done", async () => {
    const report = { submission: submission("done"), claims: [] } as unknown as Report;
    let reportCookie: string | null = null;
    server.use(
      http.get(`${API}/submissions/${ID}`, () => HttpResponse.json(submission("done"))),
      http.get(`${API}/reports/${ID}`, ({ request }) => {
        reportCookie = request.headers.get("cookie");
        return HttpResponse.json(report);
      }),
    );

    await expect(loadInitialCase(ID, "abc")).resolves.toEqual({
      submission: submission("done"),
      report,
    });
    expect(reportCookie).toBe("access_token=abc");
  });

  it.each([401, 404, 503])("returns null when the API answers %i", async (status) => {
    server.use(http.get(`${API}/submissions/${ID}`, () => new HttpResponse(null, { status })));

    await expect(loadInitialCase(ID, "abc")).resolves.toBeNull();
  });

  it("returns null when the network fails", async () => {
    server.use(http.get(`${API}/submissions/${ID}`, () => HttpResponse.error()));

    await expect(loadInitialCase(ID, "abc")).resolves.toBeNull();
  });
});
