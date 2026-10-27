import type { Metadata } from 'next';
import MarketplaceShell from '../components/MarketplaceShell';
import JsonLd from '../components/JsonLd';
import { getHomepagePreview } from '../lib/publicCatalog';
import { absoluteSiteUrl, publicPageMetadata } from '../lib/seo';

export const revalidate = 900;

export const metadata: Metadata = publicPageMetadata({
  title: 'Retail Mind | Shop Local Online',
  description: 'Discover neighbourhood shops, compare local products, and order everyday essentials with Retail Mind.',
  path: '/',
});

export default async function Home() {
  const { shops, products } = await getHomepagePreview();
  return (
    <>
      {shops.length > 0 && (
        <JsonLd data={{
          '@context': 'https://schema.org',
          '@type': 'ItemList',
          name: 'Local shops on Retail Mind',
          itemListElement: shops.slice(0, 12).map((shop, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            item: {
              '@type': 'Store',
              name: shop.shop_name,
              url: absoluteSiteUrl(`/shop/${shop.shop_id}`),
              ...(shop.city ? { address: { '@type': 'PostalAddress', addressLocality: shop.city } } : {}),
            },
          })),
        }} />
      )}
      {products.length > 0 && (
        <JsonLd data={{
          '@context': 'https://schema.org',
          '@type': 'ItemList',
          name: 'Popular products from local shops',
          itemListElement: products.slice(0, 12).map((product, index) => ({
            '@type': 'ListItem',
            position: index + 1,
            item: {
              '@type': 'Product',
              name: product.product_name,
              url: absoluteSiteUrl(`/shop/${product.shop_id}/product/${product.product_id}`),
              offers: {
                '@type': 'Offer',
                price: product.price,
                priceCurrency: 'INR',
                availability: product.stock_available === 0
                  ? 'https://schema.org/OutOfStock'
                  : 'https://schema.org/InStock',
              },
            },
          })),
        }} />
      )}
      <MarketplaceShell initialShops={shops} initialFeaturedProducts={products} />
    </>
  );
}
