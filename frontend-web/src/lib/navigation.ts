/**
 * Accept only same-origin absolute paths for post-auth navigation. This blocks
 * protocol-relative and backslash tricks without changing the existing route
 * shapes or deep-link behavior.
 */
export function safeNextPath(value: string | null | undefined, fallback = '/'): string {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) {
    return fallback;
  }
  if (value.includes('\\')) return fallback;

  try {
    const base = new URL('https://retail-mind.invalid');
    const url = new URL(value, base);
    if (url.origin !== base.origin || !url.pathname.startsWith('/')) return fallback;
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return fallback;
  }
}
