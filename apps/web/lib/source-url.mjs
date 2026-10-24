// Labels of letters, digits and inner hyphens, at least one dot: a bare domain
// with no scheme, path, port or credentials.
const DOMAIN = /^(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$/i;

/**
 * The https home page of a source's domain, or null when the value isn't a
 * bare domain (so it never becomes a link).
 * @param {string} domain
 * @returns {string | null}
 */
export function sourceUrl(domain) {
  return DOMAIN.test(domain) ? `https://${domain}` : null;
}

/**
 * An evidence link as stored, or null unless it is an absolute http(s) URL
 * (javascript:, data: and the like never become a link).
 * @param {string} url
 * @returns {string | null}
 */
export function evidenceUrl(url) {
  try {
    const { protocol } = new URL(url);
    return protocol === "http:" || protocol === "https:" ? url : null;
  } catch {
    return null;
  }
}
