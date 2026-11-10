// Requirement: rendering patterns. Data fetching for Server Components (ISR on
// /sources, SSR with streaming on /reports/[id]). The Next server talks to the
// API directly: it never goes through its own /api proxy.

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

export type ServerFetchInit = RequestInit & { next?: { revalidate?: number } };

// Throws ServerApiError on a non-OK answer or a network failure (status 0), so
// callers decide in one place what a failure means for their page.
export async function serverFetch<T>(path: string, init?: ServerFetchInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${serverApiBase()}${path}`, init);
  } catch (error) {
    throw new ServerApiError(`Network error on ${path}: ${String(error)}`, 0);
  }
  if (!response.ok) {
    throw new ServerApiError(`API answered ${response.status} on ${path}`, response.status);
  }
  return (await response.json()) as T;
}
