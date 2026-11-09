import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { requestWsTicket, socketUrl, watchSubmission } from "@/lib/submission-socket";

const API = "http://localhost:8000";
const server = setupServer();

beforeAll(() => server.listen({ onUnhandledFrame: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Stands in for the browser's WebSocket: records the URL and lets the test
// drive open/message/close by hand.
class FakeSocket {
  static instances: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: { code: number }) => void) | null = null;
  closed = false;

  constructor(public readonly url: string) {
    FakeSocket.instances.push(this);
  }

  close() {
    this.closed = true;
  }

  open() {
    this.onopen?.();
  }

  message(data: string) {
    this.onmessage?.({ data });
  }

  serverClose(code: number) {
    this.onclose?.({ code });
  }
}

const WebSocketImpl = FakeSocket as unknown as typeof WebSocket;

function setup(getTicket: (id: string) => Promise<string> = () => Promise.resolve("t+1")) {
  const onStatus = vi.fn();
  const onFallback = vi.fn();
  const stop = watchSubmission(
    "abc",
    { onStatus, onFallback },
    { wsBase: "wss://api.test/", WebSocketImpl, getTicket },
  );
  return { onStatus, onFallback, stop };
}

async function connected() {
  await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(1));
  return FakeSocket.instances[0];
}

beforeEach(() => {
  FakeSocket.instances = [];
  vi.useRealTimers();
});

describe("socketUrl", () => {
  it("puts the encoded ticket in the query", () => {
    expect(socketUrl("wss://api.test/", "abc", "t+1")).toBe(
      "wss://api.test/ws/submissions/abc?ticket=t%2B1",
    );
  });
});

describe("requestWsTicket", () => {
  it("posts with the CSRF header and returns the ticket", async () => {
    document.cookie = "csrf_token=c1; path=/";
    let csrf: string | null = null;
    server.use(
      http.post(`${API}/submissions/abc/ws-ticket`, ({ request }) => {
        csrf = request.headers.get("x-csrf-token");
        return HttpResponse.json({ ticket: "tk", expires_in: 30 });
      }),
    );

    await expect(requestWsTicket("abc")).resolves.toBe("tk");
    expect(csrf).toBe("c1");
  });
});

describe("watchSubmission", () => {
  it("falls back when there is no ws base", async () => {
    const onFallback = vi.fn();
    watchSubmission("abc", { onStatus: vi.fn(), onFallback }, { wsBase: null, WebSocketImpl });

    await vi.waitFor(() => expect(onFallback).toHaveBeenCalledTimes(1));
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("falls back when the ticket request fails", async () => {
    const { onFallback } = setup(() => Promise.reject(new Error("401")));

    await vi.waitFor(() => expect(onFallback).toHaveBeenCalledTimes(1));
    expect(FakeSocket.instances).toHaveLength(0);
  });

  it("connects with the ticket in the url", async () => {
    setup();
    expect((await connected()).url).toBe("wss://api.test/ws/submissions/abc?ticket=t%2B1");
  });

  it("forwards status events", async () => {
    const { onStatus, onFallback } = setup();
    const socket = await connected();

    socket.open();
    socket.message('{"status":"verifying","error":null}');

    expect(onStatus).toHaveBeenCalledWith({ status: "verifying", error: null });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("falls back if the socket does not open in time", async () => {
    vi.useFakeTimers();
    const { onFallback } = setup();
    await vi.waitFor(() => expect(FakeSocket.instances).toHaveLength(1));

    vi.advanceTimersByTime(5000);

    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(FakeSocket.instances[0].closed).toBe(true);
  });

  it("falls back when the socket closes before a terminal status", async () => {
    const { onFallback } = setup();
    const socket = await connected();

    socket.open();
    socket.message('{"status":"verifying","error":null}');
    socket.serverClose(1006);

    expect(onFallback).toHaveBeenCalledTimes(1);
  });

  it("does not fall back after done", async () => {
    const { onStatus, onFallback } = setup();
    const socket = await connected();

    socket.open();
    socket.message('{"status":"done","error":null}');
    socket.serverClose(1000);

    expect(onStatus).toHaveBeenCalledWith({ status: "done", error: null });
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("does not fall back after cleanup", async () => {
    const { onFallback, stop } = setup();
    const socket = await connected();

    socket.open();
    stop();
    socket.serverClose(1006);

    expect(socket.closed).toBe(true);
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("does not open a socket if cleaned up while the ticket is pending", async () => {
    let resolveTicket: (ticket: string) => void = () => {};
    const { onFallback, stop } = setup(
      () => new Promise((resolve) => (resolveTicket = resolve)),
    );

    stop();
    resolveTicket("late");
    await Promise.resolve();
    await Promise.resolve();

    expect(FakeSocket.instances).toHaveLength(0);
    expect(onFallback).not.toHaveBeenCalled();
  });

  it("falls back on a malformed message", async () => {
    const { onFallback } = setup();
    const socket = await connected();

    socket.open();
    socket.message("not json");

    expect(onFallback).toHaveBeenCalledTimes(1);
    expect(socket.closed).toBe(true);
  });

  it("falls back only once", async () => {
    const { onFallback } = setup();
    const socket = await connected();

    socket.open();
    socket.message("not json");
    socket.onerror?.();
    socket.serverClose(1006);

    expect(onFallback).toHaveBeenCalledTimes(1);
  });
});
