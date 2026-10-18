const configuredEmail = (process.env.NEXT_PUBLIC_SUPPORT_EMAIL || '').trim();

/**
 * Public support address supplied by the operator. This is never invented
 * locally; when absent, the contact route explains that no channel is set up.
 */
export const SUPPORT_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(configuredEmail)
  ? configuredEmail
  : '';
