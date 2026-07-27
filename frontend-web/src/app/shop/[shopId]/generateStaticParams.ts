import { API_BASE } from '../../../lib/api';

export async function generateStaticParams() {
  try {
    const res = await fetch(`${API_BASE}/store/shops`, { cache: 'no-store' });
    if (!res.ok) return [];

    const data = await res.json();
    const shops = Array.isArray(data?.shops) ? data.shops : [];

    return shops.map((shop: { shop_id?: number }) => ({ shopId: String(shop.shop_id) })).filter((entry: { shopId: string }) => entry.shopId);
  } catch {
    return [];
  }
}
