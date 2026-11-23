import { API_BASE } from './api';

/**
 * Normalize Render environment values. A URL pasted with surrounding quotes
 * is still valid text to Render, but cannot be used as a fetch base URL.
 */
function cleanBackendUrl(value: string | undefined): string {
  const cleaned = String(value || '')
    .trim()
    .replace(/^["']+|["']+$/g, '')
    .replace(/\/+$/, '');

  if (!cleaned) return '';

  try {
    const parsed = new URL(cleaned);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
    return cleaned;
  } catch {
    return '';
  }
}

/** The same backend URL is used by public SSR requests and API route proxies. */
export function getBackendBaseUrl(): string {
  return (
    cleanBackendUrl(process.env.RETAIL_MIND_BACKEND_URL) ||
    cleanBackendUrl(process.env.NEXT_PUBLIC_API_URL) ||
    cleanBackendUrl(API_BASE) ||
    'https://retail-mind-vkbp.onrender.com'
  );
}
