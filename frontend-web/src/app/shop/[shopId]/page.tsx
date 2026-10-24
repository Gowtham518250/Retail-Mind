import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import ShopClientPage from './ShopClientPage';
import JsonLd from '../../../components/JsonLd';
import { getPublicShopResult } from '../../../lib/publicCatalog';
import { absoluteSiteUrl, publicPageMetadata } from '../../../lib/seo';

type ShopRouteProps = { params: Promise<{ shopId: string }> };

export async function generateMetadata({ params }: ShopRouteProps): Promise<Metadata> {
  const { shopId } = await params;
  const result = await getPublicShopResult(shopId);
  if (result.notFound) notFound();
  const shop = result.shop;
  const name = shop?.shop_name || 'Neighbourhood shop';
  const description = shop?.shop_description || shop?.shop_tagline ||
    `Browse products and local availability at ${name} on Retail Mind.`;
  return publicPageMetadata({
    title: `${name} | Retail Mind`,
    description,
    path: `/shop/${shopId}`,
    image: shop?.shop_logo_url,
  });
}

export default async function ShopPage({ params }: ShopRouteProps) {
  const { shopId } = await params;
  const result = await getPublicShopResult(shopId);
  if (result.notFound) notFound();
  const shop = result.shop;
  const name = shop?.shop_name || 'Shop';
  return (
    <>
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
          { '@type': 'ListItem', position: 2, name: 'Shops', item: absoluteSiteUrl('/shops') },
          { '@type': 'ListItem', position: 3, name, item: absoluteSiteUrl(`/shop/${shopId}`) },
        ],
      }} />
      <nav aria-label="Breadcrumb" className="store-breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true"> / </span>
        <Link href="/shops">Shops</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{name}</span>
      </nav>
      <ShopClientPage shopId={Number(shopId)} initialData={shop} />
    </>
  );
}
