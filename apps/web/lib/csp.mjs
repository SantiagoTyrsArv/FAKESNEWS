/**
 * The pages' Content-Security-Policy. It is static (no per-request nonce) so
 * pages stay prerendered and served from the CDN; the price is
 * 'unsafe-inline' for scripts, which Next's inline payload and the motion
 * script in app/layout.tsx need. Everything else is closed: scripts, styles,
 * fonts and images only from this origin, network calls only to it and the
 * API, no plugins, no framing, no foreign <base> or form targets.
 * @param {{ dev: boolean, apiUrl: string }} options
 * @returns {string}
 */
export function buildCsp({ dev, apiUrl }) {
  const connect = ["'self'"];
  if (/^https?:\/\//.test(apiUrl)) connect.push(new URL(apiUrl).origin);

  const directives = [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    `connect-src ${connect.join(" ")}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ];
  // Not when the API itself is plain http (a local production build): the
  // upgrade would turn its calls into https ones that fail.
  if (!dev && !apiUrl.startsWith("http://")) directives.push("upgrade-insecure-requests");
  return directives.join("; ");
}
