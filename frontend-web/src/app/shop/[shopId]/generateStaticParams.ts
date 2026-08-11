import { getKnownShopIds } from '../../../lib/staticParams';

export async function generateStaticParams() {
  const ids = await getKnownShopIds();
  return ids.map((shopId) => ({ shopId }));
}
