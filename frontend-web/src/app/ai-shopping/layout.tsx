import type { Metadata } from 'next';
import { publicPageMetadata } from '../../lib/seo';

export const metadata: Metadata = publicPageMetadata({
  title: 'AI Shopping | Retail Mind',
  description: 'Describe what you need and compare matching products from neighbourhood shops.',
  path: '/ai-shopping',
});

export default function AiShoppingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
