import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// When set (e.g. on Vercel), the browser talks to the API through /api on the
// web's own domain, so session cookies are first-party. Needed when web and API
// live on unrelated domains such as *.vercel.app and *.up.railway.app.
// Pair it with NEXT_PUBLIC_API_URL=/api here and COOKIE_PATH_PREFIX=/api on the API.
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/+$/, "");
// Same value as API_PROXY_SECRET on the API. It proves to the API that the
// X-Client-IP header comes from this proxy, so login rate limiting is keyed on
// the visitor's real IP (see apps/api/app/core/client_ip.py). Server-only:
// never prefix it with NEXT_PUBLIC_.
const apiProxySecret = process.env.API_PROXY_SECRET;

const PROXY_SECRET_HEADER = "x-proxy-secret";
const CLIENT_IP_HEADER = "x-client-ip";

// Vercel sets x-real-ip and x-forwarded-for at its edge, overwriting whatever
// the client sent, so they hold the visitor's address.
function visitorIp(request: NextRequest): string | null {
  const realIp = request.headers.get("x-real-ip")?.trim();
  if (realIp) return realIp;
  return request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null;
}

function proxyApi(request: NextRequest, target: string) {
  const { pathname, search } = request.nextUrl;
  const url = new URL(`${target}${pathname.slice("/api".length)}${search}`);

  // Drop anything the browser sent under these names before adding our own.
  const headers = new Headers(request.headers);
  headers.delete(PROXY_SECRET_HEADER);
  headers.delete(CLIENT_IP_HEADER);
  const ip = visitorIp(request);
  if (apiProxySecret && ip) {
    headers.set(PROXY_SECRET_HEADER, apiProxySecret);
    headers.set(CLIENT_IP_HEADER, ip);
  }

  return NextResponse.rewrite(url, { request: { headers } });
}

// The UI gate below only redirects when the access_token cookie is
// absent, as a convenience so users land on /login instead of a broken
// page. In production the API must set COOKIE_DOMAIN to the shared parent
// domain, or these cookies never reach the web host. It does NOT validate the token (no signature check, no expiry
// check) — the API is the actual authorization boundary and re-validates
// the token on every request regardless of what happens here.
const PROTECTED_PREFIXES = ["/settings", "/submit", "/reports", "/history"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === "/api" || pathname.startsWith("/api/")) {
    return apiProxyTarget ? proxyApi(request, apiProxyTarget) : NextResponse.next();
  }

  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );

  if (!isProtected) {
    return NextResponse.next();
  }

  // access_token lives 15 min; csrf_token lives as long as the refresh token.
  // With only the latter left, let the page load: lib/api.ts refreshes the
  // session on the first 401 instead of bouncing the user to /login.
  const hasSession =
    request.cookies.has("access_token") || request.cookies.has("csrf_token");
  if (!hasSession) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/api/:path*",
    "/settings/:path*",
    "/submit/:path*",
    "/reports/:path*",
    "/history/:path*",
  ],
};
