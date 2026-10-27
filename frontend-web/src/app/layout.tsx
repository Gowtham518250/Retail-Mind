import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';
import './storefront-polish.css';
import './premium-v3.css';
import './retail-redesign.css';
import './experience-motion.css';
import './customer-web-refresh.css';
import './reference-design.css';
import './customer-reference-ui.css';
import './customer-motion.css';
import './fresh.css';
import './redesign.css';
import './device-motion.css';
import './living-ui.css';
import Navbar from '../components/Navbar';
import NavigationProgress from '../components/NavigationProgress';
import ScrollProgress from '../components/ScrollProgress';
import HeroParallax from '../components/HeroParallax';
import NativeAppPerformance from '../components/NativeAppPerformance';
import { CartProvider } from '../context/CartContext';
import CartDrawer from '../components/CartDrawer';
import CartBar from '../components/CartBar';
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
  keywords: [
    'shop local online',
    'local grocery delivery',
    'neighbourhood shops',
    'online grocery shopping',
    'Retail Mind',
  ],
  category: 'shopping',
  creator: SITE_NAME,
  publisher: SITE_NAME,
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
      'max-snippet': -1,
      'max-video-preview': -1,
    },
  },
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
  themeColor: '#1e4d3a',
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&display=swap"
        />
      </head>
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
            description: FALLBACK_DESCRIPTION,
            potentialAction: {
              '@type': 'SearchAction',
              target: {
                '@type': 'EntryPoint',
                urlTemplate: `${SITE_URL}/?q={search_term_string}`,
              },
              'query-input': 'required name=search_term_string',
            },
          }} />
          <NativeAppPerformance>
            <Navbar />
            <NavigationProgress />
            <ScrollProgress />
            <HeroParallax />
            <main id="main-content" tabIndex={-1} className="page-transition">{children}</main>
            <footer className="site-footer">
              <Link href="/shops">Browse shops</Link>
              <Link href="/ai-shopping">AI shopping</Link>
              <Link href="/contact">Contact</Link>
              <Link href="/privacy">Privacy information</Link>
              <AnalyticsSettings />
            </footer>
            <CartDrawer />
            <CartBar />
            <GoogleAnalytics />
          </NativeAppPerformance>
        </CartProvider>
      </body>
    </html>
  );
}
