import type { NextConfig } from "next";
import { buildCsp } from "./lib/csp.mjs";

// The /api -> API_PROXY_TARGET forwarding lives in proxy.ts, not in a rewrite
// here: it has to add the X-Client-IP / X-Proxy-Secret request headers.
// The API sends its own security headers; these cover the pages. The CSP is
// static so pages stay prerendered (see lib/csp.mjs for what that trades).
const securityHeaders = [
  {
    key: "Content-Security-Policy",
    value: buildCsp({
      dev: process.env.NODE_ENV === "development",
      apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    }),
  },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  // No "X-Powered-By: Next.js": don't advertise the stack.
  poweredByHeader: false,
  headers() {
    return Promise.resolve([{ source: "/:path*", headers: securityHeaders }]);
  },
};

export default nextConfig;
