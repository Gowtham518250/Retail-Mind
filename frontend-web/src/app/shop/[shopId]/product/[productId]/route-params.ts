import { API_BASE } from '../../../../../lib/api';
import { getKnownShopIds } from '../../../../../lib/staticParams';

/**
 * Pre-render real public product URLs when the backend is reachable at build
 * time. Dynamic params stay enabled, so new or unavailable products are still
 * server-rendered on demand without changing the backend contract.
 */
export async function getProductRouteParams() {
  const shopIds = await getKnownShopIds();
  const batches = await Promise.all(shopIds.map(async (shopId) => {
    try {
      const response = await fetch(`${API_BASE}/store/shops/${shopId}/products?limit=200`, {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) return [];
      const data = await response.json();
      if (!Array.isArray(data.products)) return [];
      return data.products
        .map((product: { id?: number }) => Number(product.id))
        .filter((productId: number) => Number.isInteger(productId) && productId > 0)
        .map((productId: number) => ({ shopId, productId: String(productId) }));
    } catch {
      return [];
    }
  }));

  return batches.flat().slice(0, 1000);
}
