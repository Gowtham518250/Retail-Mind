import type { Metadata } from 'next';
import Link from 'next/link';
import { Suspense } from 'react';
import './globals.css';
import './storefront-polish.css';
import './premium-v3.css';
import './retail-redesign.css';
import './experience-motion.css';
import Navbar from '../components/Navbar';
import NavigationProgress from '../components/NavigationProgress';
import { CartProvider } from '../context/CartContext';
import CartDrawer from '../components/CartDrawer';
import JsonLd from '../components/JsonLd';
import { FALLBACK_DESCRIPTION, FALLBACK_SOCIAL_IMAGE, SITE_NAME, SITE_URL } from '../lib/seo';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Retail Mind | Shop Local Online',
    template: '%s | Retail Mind',
  },
  applicationName: 'Retail Mind',
  description: FALLBACK_DESCRIPTION,
  alternates: { canonical: '/' },
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    title: 'Retail Mind | Shop Local Online',
    description: FALLBACK_DESCRIPTION,
    url: SITE_URL,
    images: [{ url: FALLBACK_SOCIAL_IMAGE, alt: 'Retail Mind' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Retail Mind | Shop Local Online',
    description: FALLBACK_DESCRIPTION,
    images: [FALLBACK_SOCIAL_IMAGE],
  },
  verification: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION
    ? { google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION }
    : undefined,
  manifest: '/manifest.json',
  icons: {
    icon: '/icons/retail-mind.svg',
    shortcut: '/icons/retail-mind.svg',
  },
  appleWebApp: { capable: true, statusBarStyle: 'default', title: 'Retail Mind' },
};

export const viewport = {
  themeColor: '#0f5b47',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <CartProvider>
          <JsonLd data={{
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: SITE_NAME,
            url: SITE_URL,
            logo: new URL('/icons/retail-mind.svg', SITE_URL).toString(),
          }} />
          <JsonLd data={{
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: SITE_NAME,
            url: SITE_URL,
          }} />
          <Navbar />
          <NavigationProgress />
          <main className="page-transition">
            <Suspense fallback={<div className="page-loading" role="status" aria-live="polite">Getting things ready…</div>}>{children}</Suspense>
          </main>
          <footer className="site-footer">
            <Link href="/privacy">Privacy information</Link>
          </footer>
          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
