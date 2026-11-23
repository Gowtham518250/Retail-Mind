import { NextResponse } from 'next/server';
import { API_BASE } from './api';

/**
 * Render environment values are sometimes pasted with surrounding quotes.
 * Normalize both server-only and public values in one place so SSR and route
 * handlers never point at different backends.
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

export function getBackendBaseUrl(): string {
  return (
    cleanBackendUrl(process.env.RETAIL_MIND_BACKEND_URL) ||
    cleanBackendUrl(process.env.NEXT_PUBLIC_API_URL) ||
    cleanBackendUrl(API_BASE) ||
    'https://retail-mind-vkbp.onrender.com'
  );
}

function jsonError(detail: string, status: number) {
  return NextResponse.json(
    { detail },
    { status, headers: { 'Cache-Control': 'no-store' } },
  );
}

export async function proxyBackendGet(
  path: string,
  searchParams: URLSearchParams = new URLSearchParams(),
) {
  try {
    const backendUrl = new URL(path, `${getBackendBaseUrl().replace(/\/+$/, '')}/`);
    searchParams.forEach((value, key) => backendUrl.searchParams.set(key, value));

    const response = await fetch(backendUrl, {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(20_000),
    });
    const body = await response.text();

    if (!body.trim()) {
      console.error(
        `Retail backend returned an empty body for ${path} (HTTP ${response.status}).`,
      );
      return jsonError(
        response.ok
          ? 'The retail service returned an empty response. Please retry.'
          : `The retail service could not load this shop (HTTP ${response.status}). Please retry.`,
        response.ok ? 502 : response.status,
      );
    }

    let payload: unknown;
    try {
      payload = JSON.parse(body);
    } catch {
      console.error(
        `Retail backend returned invalid JSON for ${path} (HTTP ${response.status}).`,
      );
      const unavailable = response.status >= 500;
      return jsonError(
        unavailable
          ? `The retail service is temporarily unavailable (HTTP ${response.status}). Please try again.`
          : 'The retail service returned an invalid response. Please try again.',
        unavailable ? response.status : 502,
      );
    }

    return NextResponse.json(payload, {
      status: response.status,
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch (error) {
    console.error(`Retail backend request failed for ${path}:`, error);
    return jsonError(
      'The retail service could not be reached. Check the backend URL in the customer website environment settings.',
      502,
    );
  }
}
