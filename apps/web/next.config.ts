import type { NextConfig } from "next";

// The /api -> API_PROXY_TARGET forwarding lives in proxy.ts, not in a rewrite
// here: it has to add the X-Client-IP / X-Proxy-Secret request headers.
// The API sends its own security headers; these cover the pages. No CSP yet:
// app/layout.tsx runs an inline script, so one needs a per-request nonce.
const securityHeaders = [
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
  { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
