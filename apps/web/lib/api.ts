const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function readCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function csrfHeaders(): HeadersInit {
  const csrf = readCsrfCookie();
  return csrf ? { "X-CSRF-Token": csrf } : {};
}

// Paths where a 401 means "wrong credentials / pending token", not "access
// token expired" — refreshing there would be pointless or loop.
const NO_REFRESH_PREFIXES = [
  "/auth/login",
  "/auth/register",
  "/auth/2fa/",
  "/auth/refresh",
  "/auth/logout",
];

let refreshInFlight: Promise<boolean> | null = null;

// The access token lives 15 min; long-running pages (report polling, history)
// outlive it. Rotate once via the refresh cookie and let callers retry.
// Concurrent 401s share one refresh so the rotating refresh token isn't
// spent twice (the API treats reuse as theft and revokes the family).
function refreshSession(): Promise<boolean> {
  refreshInFlight ??= fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: csrfHeaders(),
  })
    .then((res) => res.ok)
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response = await rawFetch(path, init);

  if (
    response.status === 401 &&
    !NO_REFRESH_PREFIXES.some((prefix) => path.startsWith(prefix)) &&
    (await refreshSession())
  ) {
    // Refresh also rotates the CSRF cookie, so a retried mutating request
    // must carry the new value, not the one captured before the refresh.
    const headers = new Headers(init.headers);
    if (headers.has("X-CSRF-Token")) {
      headers.set("X-CSRF-Token", readCsrfCookie() ?? "");
    }
    response = await rawFetch(path, { ...init, headers: Object.fromEntries(headers) });
  }

  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    throw new ApiError(
      (body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : response.statusText) || "Error de red",
      response.status,
      body,
    );
  }

  return body as T;
}
