import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { ServerApiError, serverApiBase, serverFetch } from "@/lib/server-api";

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
