import { NextResponse } from 'next/server';
import { getBackendBaseUrl } from './backendConfig';

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
