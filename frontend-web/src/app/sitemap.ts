import type { MetadataRoute } from 'next';
import { absoluteSiteUrl } from '../lib/seo';
import { getPublicShops } from '../lib/publicCatalog';
import { API_BASE } from '../lib/api';
import type { ShopProduct } from '../lib/types';

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const entries: MetadataRoute.Sitemap = [
    { url: absoluteSiteUrl('/'), changeFrequency: 'daily', priority: 1 },
    { url: absoluteSiteUrl('/privacy'), changeFrequency: 'yearly', priority: 0.2 },
  ];
  const shops = await getPublicShops();
  const backendBase = (
    process.env.RETAIL_MIND_BACKEND_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    API_BASE
  ).replace(/\/+$/, '');
  const productsByShop = await Promise.all(shops.map(async (shop) => {
    try {
      const response = await fetch(`${backendBase}/store/shops/${shop.shop_id}/products?limit=200`, {
        next: { revalidate: 900 },
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) return [];
      const data = await response.json();
      return (Array.isArray(data.products) ? data.products : []).map((product: ShopProduct) => ({
        url: absoluteSiteUrl(`/shop/${shop.shop_id}/product/${product.id}`),
        changeFrequency: 'weekly' as const,
        priority: 0.6,
      }));
    } catch (error) {
      console.error(`Could not load products for shop ${shop.shop_id} for sitemap generation.`, error);
      return [];
    }
  }));

  for (const shop of shops) {
    entries.push({
      url: absoluteSiteUrl(`/shop/${shop.shop_id}`),
      changeFrequency: 'weekly',
      priority: 0.7,
    });
  }
  entries.push(...productsByShop.flat());
  return entries;
}
