import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Keep the one legacy public URL shape we know about working with a real 301.
 * Only a positive numeric shop ID is accepted, so this cannot become an open
 * redirect or forward arbitrary query-string content.
 */
export function proxy(request: NextRequest) {
  if (request.nextUrl.pathname !== '/') return NextResponse.next();

  const legacyShopId = request.nextUrl.searchParams.get('shop_id');
  if (!legacyShopId || !/^[1-9]\d{0,9}$/.test(legacyShopId)) {
    return NextResponse.next();
  }

  return NextResponse.redirect(new URL(`/shop/${legacyShopId}`, request.url), 301);
}

export const config = {
  matcher: '/',
};
