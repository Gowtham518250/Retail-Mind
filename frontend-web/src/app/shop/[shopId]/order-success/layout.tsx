import { privatePageMetadata } from '../../../../lib/privatePageMetadata';

export const metadata = { ...privatePageMetadata, title: 'Order Confirmation' };

export default function OrderSuccessLayout({ children }: { children: React.ReactNode }) {
  return children;
}
