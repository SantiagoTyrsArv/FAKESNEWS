import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch, readCsrfCookie } from "@/lib/api";

const API = "http://localhost:8000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

function setCsrfCookie(value: string) {
  document.cookie = `csrf_token=${value}; path=/`;
}

beforeEach(() => {
  document.cookie = "csrf_token=; path=/; max-age=0";
});

// A protected endpoint that answers 401 until the session has been refreshed.
function expiredSession({ refreshes = true, onRefresh = () => {} } = {}) {
  let refreshed = false;
  const seenCsrf: (string | null)[] = [];
  let refreshCalls = 0;
  server.use(
    http.post(`${API}/auth/refresh`, () => {
      refreshCalls += 1;
      if (!refreshes) return new HttpResponse(null, { status: 401 });
      refreshed = true;
      onRefresh();
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(`${API}/submissions`, ({ request }) => {
      seenCsrf.push(request.headers.get("X-CSRF-Token"));
      return refreshed
        ? HttpResponse.json({ ok: true })
        : HttpResponse.json({ detail: "expirado" }, { status: 401 });
    }),
    http.get(`${API}/submissions`, () =>
      refreshed
        ? HttpResponse.json({ ok: true })
        : HttpResponse.json({ detail: "expirado" }, { status: 401 }),
    ),
  );
  return { seenCsrf, refreshCalls: () => refreshCalls };
}

describe("apiFetch", () => {
  it("returns the JSON body and sends the session cookies", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    server.use(http.get(`${API}/me`, () => HttpResponse.json({ email: "a@b.co" })));

    await expect(apiFetch("/me")).resolves.toEqual({ email: "a@b.co" });
    expect(fetchSpy.mock.calls[0][1]).toMatchObject({ credentials: "include" });
    fetchSpy.mockRestore();
  });

  it("returns null for an empty response", async () => {
    server.use(http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })));

    await expect(apiFetch("/auth/logout", { method: "POST" })).resolves.toBeNull();
  });

  it("raises the API's detail with its status and body", async () => {
    const body = { detail: "Ya tienes casos en curso." };
    server.use(http.post(`${API}/submissions`, () => HttpResponse.json(body, { status: 429 })));

    const error = await apiFetch("/submissions", { method: "POST" }).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ message: body.detail, status: 429, body });
  });

  it("raises the status text when the error is not JSON", async () => {
    server.use(
      http.get(`${API}/me`, () =>
        HttpResponse.text("<html>", { status: 502, statusText: "Bad Gateway" }),
      ),
    );

    await expect(apiFetch("/me")).rejects.toMatchObject({ message: "Bad Gateway", status: 502 });
  });

  it("refreshes an expired session once and repeats the request", async () => {
    const session = expiredSession();

    await expect(apiFetch("/submissions")).resolves.toEqual({ ok: true });
    expect(session.refreshCalls()).toBe(1);
  });

  it("shares one refresh between concurrent requests", async () => {
    // The API treats a spent refresh token as theft, so a second one would
    // sign the user out.
    const session = expiredSession();

    await Promise.all([apiFetch("/submissions"), apiFetch("/submissions"), apiFetch("/submissions")]);

    expect(session.refreshCalls()).toBe(1);
  });

  it("retries with the CSRF token the refresh rotated", async () => {
    setCsrfCookie("viejo");
    const session = expiredSession({ onRefresh: () => setCsrfCookie("nuevo") });

    await apiFetch("/submissions", {
      method: "POST",
      headers: { "X-CSRF-Token": readCsrfCookie() ?? "" },
    });

    expect(session.seenCsrf).toEqual(["viejo", "nuevo"]);
  });

  it("gives up with the original 401 when the refresh fails", async () => {
    const session = expiredSession({ refreshes: false });

    await expect(apiFetch("/submissions")).rejects.toMatchObject({ status: 401 });
    expect(session.refreshCalls()).toBe(1);
  });

  it.each(["/auth/login", "/auth/2fa/verify", "/auth/refresh"])(
    "does not refresh on a 401 from %s",
    async (path) => {
      let refreshCalls = 0;
      server.use(
        http.post(`${API}${path}`, () =>
          HttpResponse.json({ detail: "Credenciales inválidas" }, { status: 401 }),
        ),
      );
      if (path !== "/auth/refresh") {
        server.use(
          http.post(`${API}/auth/refresh`, () => {
            refreshCalls += 1;
            return new HttpResponse(null, { status: 204 });
          }),
        );
      }

      await expect(apiFetch(path, { method: "POST" })).rejects.toMatchObject({
        message: "Credenciales inválidas",
      });
      expect(refreshCalls).toBe(0);
    },
  );
});
