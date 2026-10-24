import { NextResponse } from 'next/server';
import { proxyBackendGet } from '../../../../../../lib/serverApi';

export const dynamic = 'force-dynamic';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ shopId: string }> },
) {
  const { shopId } = await params;
  if (!/^[1-9]\d*$/.test(shopId)) {
    return NextResponse.json(
      { detail: 'A valid shop ID is required.' },
      { status: 400, headers: { 'Cache-Control': 'no-store' } },
    );
  }

  return proxyBackendGet(`/store/shops/${shopId}/products`);
}
