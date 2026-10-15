'use client';

import { useParams } from 'next/navigation';
import Link from 'next/link';
import StorefrontShell from '../../../components/StorefrontShell';

export default function ShopClientPage() {
  const params = useParams();
  const shopId = Number(params?.shopId || 0);

  if (!Number.isSafeInteger(shopId) || shopId <= 0) {
    return (
      <main className="page-loading" style={{ flexDirection: 'column', gap: 12, padding: 24, textAlign: 'center' }}>
        <h1>Shop link not recognised</h1>
        <p>Choose a shop from the customer marketplace to continue shopping.</p>
        <Link href="/" style={{ color: '#5b5cf0', fontWeight: 800, textDecoration: 'underline' }}>Browse shops</Link>
      </main>
    );
  }

  return <StorefrontShell shopId={shopId} />;
}
