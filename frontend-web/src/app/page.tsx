"use client";

import { useEffect } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import MarketplaceShell from '../components/MarketplaceShell';

export default function Home() {
  const searchParams = useSearchParams();
  const router = useRouter();

  useEffect(() => {
    const requested = Number(searchParams?.get('shop_id') || '0');
    if (Number.isFinite(requested) && requested > 0) {
      router.replace('/shop/' + requested);
    }
  }, [router, searchParams]);

  const requested = Number(searchParams?.get('shop_id') || '0');
  if (Number.isFinite(requested) && requested > 0) {
    return <div className="page-loading">Opening shop…</div>;
  }

  return <MarketplaceShell />;
}
