import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ProductClientPage from './ProductClientPage';
import JsonLd from '../../../../../components/JsonLd';
import { getPublicShop, getPublicShopResult } from '../../../../../lib/publicCatalog';
import { absoluteSiteUrl, publicImageUrl, publicPageMetadata } from '../../../../../lib/seo';
import type { ShopProduct } from '../../../../../lib/types';

type ProductRouteProps = { params: Promise<{ shopId: string; productId: string }> };

async function getPublicProduct(shopId: string, productId: string): Promise<{
  shopName: string;
  shop: Awaited<ReturnType<typeof getPublicShop>>;
  product: ShopProduct | null;
  notFound: boolean;
}> {
  const result = await getPublicShopResult(shopId);
  const shop = result.shop;
  const product = shop?.products.find((item) => String(item.id) === productId) || null;
  return { shopName: shop?.shop_name || 'Local shop', shop, product, notFound: result.notFound };
}

export async function generateMetadata({ params }: ProductRouteProps): Promise<Metadata> {
  const { shopId, productId } = await params;
  const { shopName, shop, product, notFound: productNotFound } = await getPublicProduct(shopId, productId);
  if (productNotFound || (shop && !product)) notFound();
  const name = product?.name || 'Local product';
  const description = product?.description ||
    `${name} from ${shopName}. Check current availability and order on Retail Mind.`;
  return publicPageMetadata({
    title: `${name} | ${shopName}`,
    description,
    path: `/shop/${shopId}/product/${productId}`,
    image: product?.image_url,
  });
}

export default async function ProductDetailPage({ params }: ProductRouteProps) {
  const { shopId, productId } = await params;
  const { shopName, shop, product, notFound: productNotFound } = await getPublicProduct(shopId, productId);
  if (productNotFound || (shop && !product)) notFound();
  const productUrl = absoluteSiteUrl(`/shop/${shopId}/product/${productId}`);
  return (
    <>
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
          { '@type': 'ListItem', position: 2, name: 'Shops', item: absoluteSiteUrl('/shops') },
          { '@type': 'ListItem', position: 3, name: shopName, item: absoluteSiteUrl(`/shop/${shopId}`) },
          { '@type': 'ListItem', position: 4, name: product?.name || 'Product', item: productUrl },
        ],
      }} />
      {product &&
        typeof product.image_url === 'string' &&
        product.image_url.trim().length > 0 &&
        Number.isFinite(Number(product.price)) &&
        Number(product.price) > 0 && (
          <JsonLd data={{
            '@context': 'https://schema.org',
            '@type': 'Product',
            name: product.name,
            description: product.description || `${product.name} from ${shopName}.`,
            url: productUrl,
            image: [publicImageUrl(product.image_url)],
            ...(product.category ? { category: product.category } : {}),
            brand: { '@type': 'Brand', name: shopName },
            offers: {
              '@type': 'Offer',
              url: productUrl,
              price: Number(product.price),
              priceCurrency: 'INR',
              availability: product.stock_available === 0
                ? 'https://schema.org/OutOfStock'
                : 'https://schema.org/InStock',
              seller: { '@type': 'Organization', name: shopName },
            },
          }} />
        )}
      <ProductClientPage
        shopId={Number(shopId)}
        productId={Number(productId)}
        initialProduct={product}
        shopName={shopName}
      />
    </>
  );
}
