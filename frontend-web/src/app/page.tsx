import type { Metadata } from 'next';
import MarketplaceShell from '../components/MarketplaceShell';
import { getHomepagePreview } from '../lib/publicCatalog';
import { publicPageMetadata } from '../lib/seo';

export const revalidate = 900;

export const metadata: Metadata = publicPageMetadata({
  title: 'Retail Mind | Shop Local Online',
  description: 'Discover neighbourhood shops, compare local products, and order everyday essentials with Retail Mind.',
  path: '/',
});

export default async function Home() {
  const { shops, products } = await getHomepagePreview();
  return <MarketplaceShell initialShops={shops} initialFeaturedProducts={products} />;
}
