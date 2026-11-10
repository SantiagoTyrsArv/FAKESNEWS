// Requirement: postMessage. Logging out in one tab logs out every tab of the
// same origin: BroadcastChannel.postMessage carries a { type: "logout" }
// message to the other tabs, which leave private pages (see LogoutSync).
// Browsers without BroadcastChannel simply skip it: nothing breaks, the
// other tabs find out on their next request.

export const AUTH_CHANNEL = "fakesnews-auth";

interface LogoutMessage {
  type: "logout";
}

function supported(): boolean {
  return typeof BroadcastChannel !== "undefined";
}

export function announceLogout(): void {
  if (!supported()) return;
  const channel = new BroadcastChannel(AUTH_CHANNEL);
  channel.postMessage({ type: "logout" } satisfies LogoutMessage);
  channel.close();
}

export function onLogoutElsewhere(callback: () => void): () => void {
  if (!supported()) return () => {};
  const channel = new BroadcastChannel(AUTH_CHANNEL);
  channel.onmessage = (event: MessageEvent<unknown>) => {
    const data = event.data as Partial<LogoutMessage> | null;
    if (data?.type === "logout") callback();
  };
  return () => channel.close();
}
