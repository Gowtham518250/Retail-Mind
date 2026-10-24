import Link from 'next/link';
import ShopDiscoveryClient from './ShopDiscoveryClient';
import JsonLd from '../../components/JsonLd';
import { getPublicShops } from '../../lib/publicCatalog';
import { absoluteSiteUrl } from '../../lib/seo';

export default async function ShopDiscoveryPage() {
  const shops = await getPublicShops();
  return (
    <>
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
          { '@type': 'ListItem', position: 2, name: 'Shops', item: absoluteSiteUrl('/shops') },
        ],
      }} />
      <nav aria-label="Breadcrumb" className="store-breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">Shops</span>
      </nav>
      <ShopDiscoveryClient initialShops={shops} />
    </>
  );
}