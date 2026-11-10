import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { AUTH_CHANNEL } from "@/lib/auth-channel";
import { logout } from "@/lib/auth";

const API = "http://localhost:8000";
const server = setupServer();
const cleanups: Array<() => void> = [];

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => {
  server.resetHandlers();
  while (cleanups.length) cleanups.pop()?.();
});
afterAll(() => server.close());

// Another tab: a separate BroadcastChannel object on the same name.
function listen() {
  const callback = vi.fn();
  const otherTab = new BroadcastChannel(AUTH_CHANNEL);
  otherTab.onmessage = (event) => {
    if ((event.data as { type?: string } | null)?.type === "logout") callback();
  };
  cleanups.push(() => otherTab.close());
  return callback;
}

describe("logout", () => {
  it("tells the other tabs after logging out", async () => {
    server.use(http.post(`${API}/auth/logout`, () => new HttpResponse(null, { status: 204 })));
    const otherTab = listen();

    await logout();

    await vi.waitFor(() => expect(otherTab).toHaveBeenCalledTimes(1));
  });

  it("tells the other tabs even when the request fails", async () => {
    server.use(http.post(`${API}/auth/logout`, () => HttpResponse.error()));
    const otherTab = listen();

    await expect(logout()).rejects.toThrow();

    await vi.waitFor(() => expect(otherTab).toHaveBeenCalledTimes(1));
  });
});
