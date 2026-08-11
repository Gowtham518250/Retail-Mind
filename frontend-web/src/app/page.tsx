"use client";

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import StorefrontShell from '../components/StorefrontShell';

export default function Home() {
  const searchParams = useSearchParams();
  const [shopId, setShopId] = useState<number>(8);

  useEffect(() => {
    const requested = Number(searchParams?.get('shop_id') || '8');
    setShopId(Number.isFinite(requested) && requested > 0 ? requested : 8);
  }, [searchParams]);

  return <StorefrontShell shopId={shopId} />;
}
