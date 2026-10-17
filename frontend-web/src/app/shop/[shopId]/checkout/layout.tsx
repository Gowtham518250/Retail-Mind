import { privatePageMetadata } from '../../../../lib/privatePageMetadata';

export const metadata = { ...privatePageMetadata, title: 'Checkout' };

export default function CheckoutLayout({ children }: { children: React.ReactNode }) {
  return children;
}
