export const ANALYTICS_CONSENT_KEY = 'retail-mind:analytics-consent:v1';
export const OPEN_ANALYTICS_SETTINGS_EVENT = 'retail-mind:open-analytics-settings';

const configuredMeasurementId = (process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID || '').trim();

/** Only a standard GA4 web-stream ID is accepted; never send a secret here. */
export const GA_MEASUREMENT_ID = /^G-[A-Z0-9]{4,20}$/i.test(configuredMeasurementId)
  ? configuredMeasurementId.toUpperCase()
  : '';

export type AnalyticsConsent = 'granted' | 'denied';

export function readAnalyticsConsent(): AnalyticsConsent | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(ANALYTICS_CONSENT_KEY);
    return stored === 'granted' || stored === 'denied' ? stored : null;
  } catch {
    return null;
  }
}

export function writeAnalyticsConsent(value: AnalyticsConsent): void {
  try {
    window.localStorage.setItem(ANALYTICS_CONSENT_KEY, value);
  } catch {
    // Storage can be unavailable in private browsing; the in-memory choice still applies.
  }
}

function cleanParam(value: unknown): string | number | boolean | undefined {
  if (typeof value === 'string') return value.slice(0, 100);
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'boolean') return value;
  return undefined;
}

/**
 * Send only explicit, non-sensitive event fields. Analytics calls are no-ops
 * until a valid measurement ID is configured and the customer opts in.
 */
export function trackEvent(
  name: string,
  params: Record<string, unknown> = {},
): void {
  if (
    !GA_MEASUREMENT_ID
    || typeof window === 'undefined'
    || readAnalyticsConsent() !== 'granted'
    || typeof window.gtag !== 'function'
  ) return;

  const safeParams: Record<string, string | number | boolean> = {};
  for (const [key, value] of Object.entries(params)) {
    const cleaned = cleanParam(value);
    if (cleaned !== undefined) safeParams[key] = cleaned;
  }

  try {
    window.gtag('event', name, safeParams);
  } catch {
    // Analytics must never interrupt shopping.
  }
}

export function trackPageView(pathname: string, title: string): void {
  if (typeof window === 'undefined') return;
  const path = pathname.split('?')[0].split('#')[0] || '/';
  try {
    window.gtag?.('event', 'page_view', {
      page_path: path,
      page_location: `${window.location.origin}${path}`,
      page_title: title.slice(0, 120),
    });
  } catch {
    // Analytics must never interrupt navigation.
  }
}
