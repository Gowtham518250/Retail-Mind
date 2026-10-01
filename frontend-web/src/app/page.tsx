"use client";

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import StorefrontShell from '../components/StorefrontShell';
import MarketplaceShell from '../components/MarketplaceShell';

export default function Home() {
  const searchParams = useSearchParams();
  const [shopId, setShopId] = useState<number | null>(null);

  useEffect(() => {
    const raw = searchParams?.get('shop_id');
    const requested = raw ? Number(raw) : NaN;
    setShopId(Number.isFinite(requested) && requested > 0 ? requested : null);
  }, [searchParams]);

  return shopId ? <StorefrontShell shopId={shopId} /> : <MarketplaceShell />;
}
