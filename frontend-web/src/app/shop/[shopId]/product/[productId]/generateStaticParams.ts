import { getProductRouteParams } from './route-params';

export async function generateStaticParams() {
  return getProductRouteParams();
}
