import ShopDiscoveryClient from './ShopDiscoveryClient';
import { getPublicShops } from '../../lib/publicCatalog';

export default async function ShopDiscoveryPage() {
  const shops = await getPublicShops();
  return <ShopDiscoveryClient initialShops={shops} />;
}
