import { NextResponse } from 'next/server';
import { proxyBackendGet } from '../../../../lib/serverApi';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const incoming = new URL(request.url);
  const query = (incoming.searchParams.get('q') || '').trim();
  const mode = incoming.searchParams.get('mode') || 'all';
  const requestedLimit = Number.parseInt(incoming.searchParams.get('limit') || '30', 10);

  if (query.length > 120) {
    return NextResponse.json(
      { detail: 'Search terms must be 120 characters or fewer.' },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  if (!['all', 'shops', 'products'].includes(mode)) {
    return NextResponse.json(
      { detail: 'Choose a valid marketplace search mode.' },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  const limit = Number.isFinite(requestedLimit)
    ? Math.min(60, Math.max(1, requestedLimit))
    : 30;
  const backendParams = new URLSearchParams({ mode, limit: String(limit) });
  if (query) backendParams.set('q', query);

  return proxyBackendGet('/store/marketplace/search', backendParams);
}
