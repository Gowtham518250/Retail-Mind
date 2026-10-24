import { cache } from 'react';
import { API_BASE } from './api';
import type { ShopResponse } from './types';

export interface PublicShop {
  shop_id: number;
  shop_name: string;
  shop_type?: string;
  tagline?: string;
  description?: string;
  logo_url?: string | null;
  address?: string;
  city?: string;
  state?: string;
  categories?: string[] | string | null;
  rating?: number | null;
  rating_count?: number | null;
}

export interface PublicProductPreview {
  product_id: number;
  product_name: string;
  shop_id: number;
  shop_name: string;
  price: number;
  image_url?: string | null;
  category?: string;
  description?: string;
  stock_available?: number;
}

const backendBase = (
  process.env.RETAIL_MIND_BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  API_BASE
).replace(/\/+$/, '');

export async function getPublicShops(): Promise<PublicShop[]> {
  try {
    const response = await fetch(`${backendBase}/store/shops?limit=200`, {
      next: { revalidate: 3600 },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      console.error(`Could not load public shops for SEO rendering (HTTP ${response.status}).`);
      return [];
    }
    const data = await response.json();
    return Array.isArray(data.shops) ? data.shops : [];
  } catch (error) {
    console.error('Could not load public shops for SEO rendering.', error);
    return [];
  }
}

const fetchShopPreview = cache(async (shop: PublicShop): Promise<PublicProductPreview[]> => {
  try {
    const response = await fetch(`${backendBase}/store/shops/${shop.shop_id}/products?limit=8`, {
      next: { revalidate: 900 },
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      console.error(`Could not load products for shop ${shop.shop_id} for the homepage (HTTP ${response.status}).`);
      return [];
    }
    const data = await response.json();
    if (!Array.isArray(data.products)) return [];
    return data.products
      .map((product: Record<string, unknown>) => ({
        product_id: Number(product.id),
        product_name: String(product.name ?? '').trim(),
        shop_id: shop.shop_id,
        shop_name: String(data.shop_name || shop.shop_name),
        price: Number(product.price),
        image_url: typeof product.image_url === 'string' ? product.image_url : null,
        category: typeof product.category === 'string' ? product.category : '',
        description: typeof product.description === 'string' ? product.description : '',
        stock_available: Number(product.stock_available ?? 0),
      }))
      .filter((product: PublicProductPreview) => (
        Number.isFinite(product.product_id)
        && product.product_id > 0
        && product.product_name.length > 0
        && Number.isFinite(product.price)
      ));
  } catch (error) {
    console.error(`Could not load products for shop ${shop.shop_id} for the homepage.`, error);
    return [];
  }
});

/**
 * Server-render a useful marketplace preview. Only public, online-enabled
 * shop data is fetched, and the same fetch cache is shared by the homepage
 * metadata and rendering pass.
 */
export async function getHomepagePreview(): Promise<{
  shops: PublicShop[];
  products: PublicProductPreview[];
}> {
  const shops = await getPublicShops();
  if (!shops.length) return { shops: [], products: [] };

  const batches = await Promise.all(shops.slice(0, 6).map((shop) => fetchShopPreview(shop)));
  const seen = new Set<string>();
  const products = batches.flat().filter((product) => {
    const key = `${product.shop_id}:${product.product_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  }).slice(0, 12);

  return { shops, products };
}

const fetchPublicShop = cache(async (shopId: string): Promise<{
  shop: ShopResponse | null;
  notFound: boolean;
}> => {
  if (!/^\d+$/.test(shopId)) return { shop: null, notFound: true };
  try {
    const response = await fetch(`${backendBase}/store/shops/${shopId}/products?limit=200`, {
      next: { revalidate: 900 },
      signal: AbortSignal.timeout(8000),
    });
    if (response.status === 404) return { shop: null, notFound: true };
    if (!response.ok) {
      console.error(`Could not load public shop ${shopId} (HTTP ${response.status}).`);
      return { shop: null, notFound: false };
    }
    return { shop: await response.json() as ShopResponse, notFound: false };
  } catch (error) {
    console.error(`Could not load public shop ${shopId} for SEO rendering.`, error);
    return { shop: null, notFound: false };
  }
});

export function getPublicShopResult(shopId: string | number) {
  return fetchPublicShop(String(shopId));
}

export async function getPublicShop(shopId: string | number): Promise<ShopResponse | null> {
  return (await getPublicShopResult(shopId)).shop;
}
