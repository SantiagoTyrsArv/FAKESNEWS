// Requirement: WebSockets (client side). The report page follows a case's
// progress over a WebSocket to the API instead of polling it every 2 s.
//
// Vercel's /api proxy can't carry a WebSocket and the session cookie is
// first-party to the web's domain, so the browser:
//   1. asks for a single-use ticket through /api (the httpOnly cookie
//      authenticates that request), then
//   2. connects to `${NEXT_PUBLIC_WS_URL}/ws/submissions/{id}?ticket=...`.
// The API checks the Origin header, spends the ticket and checks the case is
// the user's (apps/api/app/modules/submissions/live.py).
//
// Whenever the socket can't do the job (no URL configured, no ticket, the API
// waking up from scale-to-zero, a dropped connection, a bad message) it calls
// onFallback once and the page goes back to polling.
import { apiFetch, csrfHeaders, WS_BASE_URL } from "@/lib/api";
import { TERMINAL_STATUSES, type SubmissionStatus } from "@/lib/cases";

export interface StatusEvent {
  status: SubmissionStatus;
  error: string | null;
}

const OPEN_TIMEOUT_MS = 5000;

export async function requestWsTicket(id: string): Promise<string> {
  const { ticket } = await apiFetch<{ ticket: string; expires_in: number }>(
    `/submissions/${encodeURIComponent(id)}/ws-ticket`,
    { method: "POST", headers: csrfHeaders() },
  );
  return ticket;
}

export function socketUrl(base: string, id: string, ticket: string): string {
  let end = base.length;
  while (end > 0 && base[end - 1] === "/") end--;
  return `${base.slice(0, end)}/ws/submissions/${encodeURIComponent(id)}?ticket=${encodeURIComponent(ticket)}`;
}

function parseEvent(data: unknown): StatusEvent | null {
  if (typeof data !== "string") return null;
  try {
    const value: unknown = JSON.parse(data);
    if (
      typeof value === "object" &&
      value !== null &&
      typeof (value as StatusEvent).status === "string" &&
      ((value as StatusEvent).error === null || typeof (value as StatusEvent).error === "string")
    ) {
      return { status: (value as StatusEvent).status, error: (value as StatusEvent).error };
    }
  } catch {
    // Falls through to null.
  }
  return null;
}

export function watchSubmission(
  id: string,
  handlers: { onStatus: (event: StatusEvent) => void; onFallback: () => void },
  options: {
    wsBase?: string | null;
    openTimeoutMs?: number;
    WebSocketImpl?: typeof WebSocket;
    getTicket?: (id: string) => Promise<string>;
  } = {},
): () => void {
  const wsBase = options.wsBase === undefined ? WS_BASE_URL : options.wsBase;
  const openTimeoutMs = options.openTimeoutMs ?? OPEN_TIMEOUT_MS;
  const WebSocketImpl = options.WebSocketImpl ?? globalThis.WebSocket;
  const getTicket = options.getTicket ?? requestWsTicket;

  let stopped = false;
  let finished = false;
  let socket: WebSocket | null = null;
  let openTimer: ReturnType<typeof setTimeout> | undefined;

  function end() {
    clearTimeout(openTimer);
    if (socket) {
      socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
      socket.close();
    }
  }

  function fallback() {
    if (stopped || finished) return;
    finished = true;
    end();
    handlers.onFallback();
  }

  if (!wsBase || !WebSocketImpl) {
    queueMicrotask(fallback);
  } else {
    getTicket(id).then(
      (ticket) => {
        if (stopped || finished) return;
        socket = new WebSocketImpl(socketUrl(wsBase, id, ticket));
        openTimer = setTimeout(fallback, openTimeoutMs);
        socket.onopen = () => clearTimeout(openTimer);
        socket.onmessage = (message: MessageEvent) => {
          const event = parseEvent(message.data);
          if (!event) {
            fallback();
            return;
          }
          if (TERMINAL_STATUSES.includes(event.status)) {
            finished = true;
            end();
          }
          handlers.onStatus(event);
        };
        socket.onerror = fallback;
        socket.onclose = fallback;
      },
      fallback,
    );
  }

  return () => {
    stopped = true;
    end();
  };
}
