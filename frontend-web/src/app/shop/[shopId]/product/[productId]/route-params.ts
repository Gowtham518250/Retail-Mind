import { API_BASE } from '../../../../../lib/api';

export async function getProductRouteParams() {
  try {
    const res = await fetch(`${API_BASE}/store/shops`, { cache: 'no-store' });
    if (!res.ok) return [];

    const data = await res.json();
    const shops = Array.isArray(data?.shops) ? data.shops : [];

    return shops.flatMap((shop: { shop_id?: number }) => {
      const shopId = shop.shop_id;
      if (!shopId) return [];
      return [{ shopId: String(shopId), productId: '1' }];
    });
  } catch {
    return [];
  }
}
