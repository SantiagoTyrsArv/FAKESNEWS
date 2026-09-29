import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// This only gates the UI: it redirects when the access_token cookie is
// absent, as a convenience so users land on /login instead of a broken
// page. It does NOT validate the token (no signature check, no expiry
// check) — the API is the actual authorization boundary and re-validates
// the token on every request regardless of what happens here.
const PROTECTED_PREFIXES = ["/settings", "/submit", "/reports", "/history"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );

  if (!isProtected) {
    return NextResponse.next();
  }

  const hasAccessToken = request.cookies.has("access_token");
  if (!hasAccessToken) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/settings/:path*", "/submit/:path*", "/reports/:path*", "/history/:path*"],
};
