import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ProductClientPage from './ProductClientPage';
import { getPublicShop, getPublicShopResult } from '../../../../../lib/publicCatalog';
import { publicPageMetadata } from '../../../../../lib/seo';
import type { ShopProduct } from '../../../../../lib/types';

export { generateStaticParams } from './generateStaticParams';

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
  const { shopName, product } = await getPublicProduct(shopId, productId);
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
  return (
    <ProductClientPage
      shopId={Number(shopId)}
      productId={Number(productId)}
      initialProduct={product}
      shopName={shopName}
    />
  );
}
