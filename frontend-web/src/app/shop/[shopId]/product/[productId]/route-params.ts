import { getKnownShopIds } from '../../../../../lib/staticParams';

export async function getProductRouteParams() {
  const shopIds = await getKnownShopIds();
  return shopIds.map((shopId) => ({ shopId, productId: '1' }));
}
