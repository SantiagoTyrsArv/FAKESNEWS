// Requirement: postMessage. Logging out in one tab logs out every tab of the
// same origin: BroadcastChannel.postMessage carries a { type: "logout" }
// message to the other tabs, which leave private pages (see LogoutSync).
// Browsers without BroadcastChannel simply skip it: nothing breaks, the
// other tabs find out on their next request.

export const AUTH_CHANNEL = "fakesnews-auth";

interface LogoutMessage {
  type: "logout";
}

// One channel object per tab, used both to post and to listen. A message
// reaches every *other* BroadcastChannel object of the same name, so the tab
// that logs out never hears its own message (it is already going to /login).
let channel: BroadcastChannel | null = null;

function tabChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === "undefined") return null;
  channel ??= new BroadcastChannel(AUTH_CHANNEL);
  return channel;
}

export function announceLogout(): void {
  tabChannel()?.postMessage({ type: "logout" } satisfies LogoutMessage);
}

export function onLogoutElsewhere(callback: () => void): () => void {
  const tab = tabChannel();
  if (!tab) return () => {};
  const listener = (event: MessageEvent<unknown>) => {
    const data = event.data as Partial<LogoutMessage> | null;
    if (data?.type === "logout") callback();
  };
  tab.addEventListener("message", listener);
  return () => tab.removeEventListener("message", listener);
}
