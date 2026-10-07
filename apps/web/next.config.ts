import type { NextConfig } from "next";

// When set (e.g. on Vercel), the browser talks to the API through /api on the
// web's own domain, so session cookies are first-party. Needed when web and API
// live on unrelated domains such as *.vercel.app and *.up.railway.app.
// Pair it with NEXT_PUBLIC_API_URL=/api here and COOKIE_PATH_PREFIX=/api on the API.
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/+$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [{ source: "/api/:path*", destination: `${apiProxyTarget}/:path*` }];
  },
};

export default nextConfig;
