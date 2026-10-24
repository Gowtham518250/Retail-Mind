import { privatePageMetadata } from '../../lib/privatePageMetadata';

export const metadata = { ...privatePageMetadata, title: 'Sign in' };

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
