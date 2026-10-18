import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';
import './storefront-polish.css';
import './premium-v3.css';
import './retail-redesign.css';
import './experience-motion.css';
import Navbar from '../components/Navbar';
import NavigationProgress from '../components/NavigationProgress';
import NativeAppPerformance from '../components/NativeAppPerformance';
import { CartProvider } from '../context/CartContext';
import CartDrawer from '../components/CartDrawer';
import JsonLd from '../components/JsonLd';
import GoogleAnalytics from '../components/GoogleAnalytics';
import AnalyticsSettings from '../components/AnalyticsSettings';
import { SUPPORT_EMAIL } from '../lib/support';
import {
  FALLBACK_DESCRIPTION,
  FALLBACK_SOCIAL_IMAGE,
  FALLBACK_SOCIAL_IMAGE_HEIGHT,
  FALLBACK_SOCIAL_IMAGE_WIDTH,
  SITE_NAME,
  SITE_URL,
} from '../lib/seo';

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: 'Retail Mind | Shop Local Online',
    template: '%s | Retail Mind',
  },
  applicationName: 'Retail Mind',
  description: FALLBACK_DESCRIPTION,
  openGraph: {
    type: 'website',
    siteName: SITE_NAME,
    title: 'Retail Mind | Shop Local Online',
    description: FALLBACK_DESCRIPTION,
    url: SITE_URL,
    images: [{
      url: FALLBACK_SOCIAL_IMAGE,
      alt: 'Retail Mind — shop local online',
      width: FALLBACK_SOCIAL_IMAGE_WIDTH,
      height: FALLBACK_SOCIAL_IMAGE_HEIGHT,
      type: 'image/png',
    }],
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
  themeColor: '#143b2c',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <CartProvider>
          <JsonLd data={{
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: SITE_NAME,
            url: SITE_URL,
            logo: {
              '@type': 'ImageObject',
              url: new URL('/icons/retail-mind-logo.png', SITE_URL).toString(),
              width: 512,
              height: 512,
            },
            ...(SUPPORT_EMAIL
              ? {
                  contactPoint: {
                    '@type': 'ContactPoint',
                    contactType: 'customer support',
                    email: SUPPORT_EMAIL,
                  },
                }
              : {}),
          }} />
          <JsonLd data={{
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: SITE_NAME,
            url: SITE_URL,
          }} />
          <NativeAppPerformance>
            <Navbar />
            <NavigationProgress />
            <main id="main-content" tabIndex={-1} className="page-transition">{children}</main>
            <footer className="site-footer">
              <Link href="/shops">Browse shops</Link>
              <Link href="/ai-shopping">AI shopping</Link>
              <Link href="/contact">Contact</Link>
              <Link href="/privacy">Privacy information</Link>
              <AnalyticsSettings />
            </footer>
            <CartDrawer />
            <GoogleAnalytics />
          </NativeAppPerformance>
        </CartProvider>
      </body>
    </html>
  );
}
