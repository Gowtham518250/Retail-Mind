import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import MarketplaceShell from '../components/MarketplaceShell';
import { publicPageMetadata } from '../lib/seo';

export const metadata: Metadata = publicPageMetadata({
  title: 'Retail Mind | Shop Local Online',
  description: 'Discover neighbourhood shops, compare local products, and order everyday essentials with Retail Mind.',
  path: '/',
});

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ shop_id?: string | string[] }>;
}) {
  const params = await searchParams;
  const requestedShop = Array.isArray(params.shop_id) ? params.shop_id[0] : params.shop_id;
  if (requestedShop && /^\d+$/.test(requestedShop) && Number(requestedShop) > 0) {
    redirect(`/shop/${requestedShop}`);
  }
  return <MarketplaceShell />;
}
