import type { Metadata } from 'next';
import { publicPageMetadata } from '../../lib/seo';

export const metadata: Metadata = publicPageMetadata({
  title: 'Local Shops | Retail Mind',
  description: 'Discover neighbourhood shops on Retail Mind and browse the products listed by each local storefront.',
  path: '/shops',
});

export default function ShopsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
