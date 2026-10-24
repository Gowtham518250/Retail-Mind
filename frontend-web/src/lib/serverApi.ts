import { NextResponse } from 'next/server';

const BACKEND_BASE = (
  process.env.RETAIL_MIND_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://retail-mind-hpx3.onrender.com'
).replace(/\/+$/, '');

export async function proxyBackendGet(path: string, searchParams: URLSearchParams = new URLSearchParams()) {
  const backendUrl = new URL(path, BACKEND_BASE);
  searchParams.forEach((value, key) => backendUrl.searchParams.set(key, value));

  try {
    const response = await fetch(backendUrl, {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json' },
      signal: AbortSignal.timeout(20_000),
    });
    const body = await response.text();

    let payload: unknown;
    try {
      payload = body ? JSON.parse(body) : {};
    } catch {
      console.error(`Retail backend returned invalid JSON for ${path} (HTTP ${response.status}).`);
      const unavailable = response.status >= 500;
      return NextResponse.json(
        {
          detail: unavailable
            ? `The retail service is temporarily unavailable (HTTP ${response.status}). Please try again.`
            : 'The retail service returned an invalid response. Please try again.',
        },
        {
          status: unavailable ? response.status : 502,
          headers: { 'Cache-Control': 'no-store' },
        },
      );
    }

    return NextResponse.json(payload, {
      status: response.status,
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch (error) {
    console.error(`Retail backend request failed for ${path}:`, error);
    return NextResponse.json(
      { detail: 'The retail service is temporarily unavailable. Please try again.' },
      { status: 502, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}
