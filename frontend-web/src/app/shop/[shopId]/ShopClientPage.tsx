'use client';

import StorefrontShell from '../../../components/StorefrontShell';
import type { ShopResponse } from '../../../lib/types';

export default function ShopClientPage({
  shopId,
  initialData,
}: {
  shopId: number;
  initialData: ShopResponse | null;
}) {
  return <StorefrontShell shopId={shopId} initialData={initialData} />;
}
