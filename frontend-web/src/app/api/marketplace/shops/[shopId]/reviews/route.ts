import { NextResponse } from 'next/server';
import { proxyBackendGet } from '../../../../../../lib/serverApi';

export const dynamic = 'force-dynamic';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ shopId: string }> },
) {
  const { shopId } = await params;
  if (!/^[1-9]\d*$/.test(shopId)) {
    return NextResponse.json(
      { detail: 'A valid shop ID is required.' },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  const incoming = new URL(request.url);
  const requestedLimit = Number.parseInt(incoming.searchParams.get('limit') || '20', 10);
  const limit = Number.isFinite(requestedLimit)
    ? Math.min(200, Math.max(1, requestedLimit))
    : 20;

  return proxyBackendGet(
    `/store/shops/${shopId}/reviews`,
    new URLSearchParams({ limit: String(limit) }),
  );
}
