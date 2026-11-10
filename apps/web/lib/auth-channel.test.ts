import { afterEach, describe, expect, it, vi } from "vitest";
import { AUTH_CHANNEL, announceLogout, onLogoutElsewhere } from "@/lib/auth-channel";

// Node's BroadcastChannel delivers messages between instances of the same
// process, which stands in for two tabs of the same origin.
const cleanups: Array<() => void> = [];

function listen(callback: () => void) {
  const unsubscribe = onLogoutElsewhere(callback);
  cleanups.push(unsubscribe);
  return unsubscribe;
}

afterEach(() => {
  while (cleanups.length) cleanups.pop()?.();
  vi.unstubAllGlobals();
});

describe("auth channel", () => {
  it("announces logout to other listeners", async () => {
    const callback = vi.fn();
    listen(callback);

    announceLogout();

    await vi.waitFor(() => expect(callback).toHaveBeenCalledTimes(1));
  });

  it("ignores other messages", async () => {
    const callback = vi.fn();
    listen(callback);

    const other = new BroadcastChannel(AUTH_CHANNEL);
    other.postMessage({ type: "x" });
    other.postMessage(null);
    other.postMessage({ type: "logout" });

    // Messages from one sender arrive in order: once the logout is in, the
    // two earlier messages have been seen and must not have counted.
    await vi.waitFor(() => expect(callback).toHaveBeenCalled());
    expect(callback).toHaveBeenCalledTimes(1);
    other.close();
  });

  it("unsubscribe stops callbacks", async () => {
    const stopped = vi.fn();
    const witness = vi.fn();
    const unsubscribe = listen(stopped);
    listen(witness);

    unsubscribe();
    announceLogout();

    await vi.waitFor(() => expect(witness).toHaveBeenCalledTimes(1));
    expect(stopped).not.toHaveBeenCalled();
  });

  it("is a no-op without BroadcastChannel", () => {
    vi.stubGlobal("BroadcastChannel", undefined);
    const callback = vi.fn();

    expect(() => announceLogout()).not.toThrow();
    const unsubscribe = onLogoutElsewhere(callback);
    expect(() => unsubscribe()).not.toThrow();
    expect(callback).not.toHaveBeenCalled();
  });
});
