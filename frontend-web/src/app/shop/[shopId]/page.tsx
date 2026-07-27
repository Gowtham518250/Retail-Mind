'use client';

import { useParams } from 'next/navigation';
import StorefrontShell from '../../../components/StorefrontShell';

export default function ShopPage() {
  const params = useParams();
  const shopId = Number(params?.shopId || 8);

  return <StorefrontShell shopId={Number.isFinite(shopId) && shopId > 0 ? shopId : 8} />;
}
