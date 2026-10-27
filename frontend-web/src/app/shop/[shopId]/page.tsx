import type { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import ShopClientPage from './ShopClientPage';
import JsonLd from '../../../components/JsonLd';
import { getPublicShopResult } from '../../../lib/publicCatalog';
import { absoluteSiteUrl, publicImageUrl, publicPageMetadata } from '../../../lib/seo';

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
      {shop && (
        <JsonLd data={{
          '@context': 'https://schema.org',
          '@type': 'Store',
          name: shop.shop_name,
          url: absoluteSiteUrl(`/shop/${shopId}`),
          description: shop.shop_description || shop.shop_tagline || `Shop online from ${shop.shop_name}.`,
          ...(shop.shop_logo_url ? { image: publicImageUrl(shop.shop_logo_url) } : {}),
          ...(shop.shop_phone ? { telephone: shop.shop_phone } : {}),
          ...(shop.shop_email ? { email: shop.shop_email } : {}),
          ...(shop.shop_address || shop.shop_city || shop.shop_state
            ? {
                address: {
                  '@type': 'PostalAddress',
                  ...(shop.shop_address ? { streetAddress: shop.shop_address } : {}),
                  ...(shop.shop_city ? { addressLocality: shop.shop_city } : {}),
                  ...(shop.shop_state ? { addressRegion: shop.shop_state } : {}),
                  ...(shop.shop_postal_code ? { postalCode: shop.shop_postal_code } : {}),
                },
              }
            : {}),
          ...(Number(shop.rating_count || 0) > 0 && Number(shop.rating || 0) > 0
            ? {
                aggregateRating: {
                  '@type': 'AggregateRating',
                  ratingValue: Number(shop.rating || 0),
                  reviewCount: Number(shop.rating_count),
                },
              }
            : {}),
        }} />
      )}
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
