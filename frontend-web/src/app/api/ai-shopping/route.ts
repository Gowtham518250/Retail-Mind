import { NextResponse } from 'next/server';

const BACKEND_BASE = (
  process.env.RETAIL_MIND_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  'https://retail-mind-vkbp.onrender.com'
).replace(/\/+$/, '');

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const q = (incoming.searchParams.get('q') || '').trim();
  const limit = incoming.searchParams.get('limit') || '10';

  if (q.length < 2) {
    return NextResponse.json(
      {
        available: false,
        query: q,
        message: 'Enter at least 2 characters to search Shopping AI.',
        recommendations: [],
      },
      {
        status: 400,
        headers: { 'Cache-Control': 'no-store' },
      },
    );
  }

  const backendUrl = new URL('/store/customer-ai', BACKEND_BASE);
  backendUrl.searchParams.set('q', q);
  backendUrl.searchParams.set('limit', limit);

  try {
    const response = await fetch(backendUrl.toString(), {
      method: 'GET',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
      },
      signal: AbortSignal.timeout(20_000),
    });

    const text = await response.text();
    let payload: unknown = {};
    try {
      payload = text ? JSON.parse(text) : {};
    } catch {
      payload = {
        detail:
          response.status >= 500
            ? 'Shopping AI backend returned an invalid server response.'
            : 'Shopping AI returned an invalid response.',
      };
    }

    return NextResponse.json(payload, {
      status: response.status,
      headers: {
        'Cache-Control': 'no-store',
      },
    });
  } catch (error) {
    console.error('Shopping AI proxy request failed:', error);
    return NextResponse.json(
      {
        available: null,
        query: q,
        recommendations: [],
        detail:
          'Shopping AI could not reach the retail backend right now. Please try again in a moment.',
        code: 'AI_BACKEND_UNREACHABLE',
      },
      {
        status: 502,
        headers: { 'Cache-Control': 'no-store' },
      },
    );
  }
}
