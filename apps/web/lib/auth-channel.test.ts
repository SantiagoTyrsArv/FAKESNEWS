import { afterEach, describe, expect, it, vi } from "vitest";
import { AUTH_CHANNEL, announceLogout, onLogoutElsewhere } from "@/lib/auth-channel";

// Node's BroadcastChannel delivers messages between instances of the same
// process: a bare `new BroadcastChannel(AUTH_CHANNEL)` stands in for another
// tab, while the module's own functions are this tab.
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
  it("hears a logout from another tab", async () => {
    const callback = vi.fn();
    listen(callback);

    const otherTab = new BroadcastChannel(AUTH_CHANNEL);
    otherTab.postMessage({ type: "logout" });

    await vi.waitFor(() => expect(callback).toHaveBeenCalledTimes(1));
    otherTab.close();
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
    const otherTab = new BroadcastChannel(AUTH_CHANNEL);
    otherTab.postMessage({ type: "logout" });

    await vi.waitFor(() => expect(witness).toHaveBeenCalledTimes(1));
    expect(stopped).not.toHaveBeenCalled();
    otherTab.close();
  });

  it("the tab that logs out does not hear its own message", async () => {
    // In a browser, a message reaches every other BroadcastChannel object of
    // the same name, including those in the sending tab. This tab's listener
    // must not react: it is already on its way to /login.
    const sameTab = vi.fn();
    listen(sameTab);
    const otherTab = new BroadcastChannel(AUTH_CHANNEL);
    const received = vi.fn();
    otherTab.onmessage = (event) => received(event.data);

    announceLogout();

    await vi.waitFor(() => expect(received).toHaveBeenCalledWith({ type: "logout" }));
    expect(sameTab).not.toHaveBeenCalled();
    otherTab.close();
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
