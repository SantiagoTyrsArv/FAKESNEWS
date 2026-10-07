import type { NextConfig } from "next";

// The /api -> API_PROXY_TARGET forwarding lives in proxy.ts, not in a rewrite
// here: it has to add the X-Client-IP / X-Proxy-Secret request headers.
const nextConfig: NextConfig = {};

export default nextConfig;
