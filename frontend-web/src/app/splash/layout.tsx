import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Welcome to Retail Mind',
  description: 'Welcome to Retail Mind, your neighbourhood shopping experience.',
  robots: {
    index: false,
    follow: true,
    googleBot: {
      index: false,
      follow: true,
    },
  },
};

export default function SplashLayout({ children }: { children: React.ReactNode }) {
  return children;
}
