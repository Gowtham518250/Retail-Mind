import { privatePageMetadata } from '../../lib/privatePageMetadata';

export const metadata = { ...privatePageMetadata, title: 'Your Account' };

export default function ProfileLayout({ children }: { children: React.ReactNode }) {
  return children;
}
