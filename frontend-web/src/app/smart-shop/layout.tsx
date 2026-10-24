import { privatePageMetadata } from '../../lib/privatePageMetadata';

export const metadata = { ...privatePageMetadata, title: 'Smart Shopping' };

export default function SmartShopLayout({ children }: { children: React.ReactNode }) {
  return children;
}
