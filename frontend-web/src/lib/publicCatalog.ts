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
