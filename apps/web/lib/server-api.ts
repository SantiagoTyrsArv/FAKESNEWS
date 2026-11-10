// Requirement: rendering patterns. Data fetching for Server Components (ISR on
// /sources, SSR with streaming on /reports/[id]). The Next server talks to the
// API directly: it never goes through its own /api proxy.

import type { Report, Submission } from "@/lib/cases";

const LOCAL_API = "http://localhost:8000";

type Env = Readonly<Record<string, string | undefined>>;

// A loop instead of /\/+$/, whose backtracking is super-linear on long input.
function withoutTrailingSlashes(url: string): string {
  let end = url.length;
  while (end > 0 && url[end - 1] === "/") end--;
  return url.slice(0, end);
}

export function serverApiBase(env: Env = process.env): string {
  if (env.API_PROXY_TARGET) return withoutTrailingSlashes(env.API_PROXY_TARGET);
  const publicUrl = env.NEXT_PUBLIC_API_URL;
  if (publicUrl && /^https?:\/\//.test(publicUrl)) return withoutTrailingSlashes(publicUrl);
  return LOCAL_API;
}

export class ServerApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ServerApiError";
    this.status = status;
  }
}

// A page waits on this fetch: an API that hangs (or takes long to wake from
// scale to zero) must not keep the <Suspense> fallback on screen until the
// function times out. Giving up turns into the usual client-side fallback.
const TIMEOUT_MS = 8000;

export type ServerFetchInit = RequestInit & {
  next?: { revalidate?: number };
  timeoutMs?: number;
};

// Throws ServerApiError on a non-OK answer, a network failure or a timeout
// (status 0), so callers decide in one place what a failure means for their page.
export async function serverFetch<T>(path: string, init: ServerFetchInit = {}): Promise<T> {
  const { timeoutMs = TIMEOUT_MS, ...requestInit } = init;
  let response: Response;
  try {
    response = await fetch(`${serverApiBase()}${path}`, {
      ...requestInit,
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch (error) {
    throw new ServerApiError(`Network error on ${path}: ${String(error)}`, 0);
  }
  if (!response.ok) {
    throw new ServerApiError(`API answered ${response.status} on ${path}`, response.status);
  }
  return (await response.json()) as T;
}

// Requirement: rendering patterns — SSR. The first render of /reports/[id]
// carries the case, read with the visitor's access_token cookie (only that
// one: the API needs nothing else). Any failure (expired token, which the
// server can't renew; 404; API down) returns null and the page falls back to
// the client fetch, which renews the session in the browser.
export async function loadInitialCase(
  id: string,
  accessToken: string | undefined,
): Promise<{ submission: Submission; report: Report | null } | null> {
  if (!accessToken) return null;
  const init: ServerFetchInit = {
    cache: "no-store",
    headers: { cookie: `access_token=${accessToken}` },
  };
  const path = encodeURIComponent(id);
  try {
    const submission = await serverFetch<Submission>(`/submissions/${path}`, init);
    const report =
      submission.status === "done" ? await serverFetch<Report>(`/reports/${path}`, init) : null;
    return { submission, report };
  } catch (error) {
    if (error instanceof ServerApiError) return null;
    throw error;
  }
}
