import { privatePageMetadata } from '../../lib/privatePageMetadata';

export const metadata = privatePageMetadata;

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return children;
}
