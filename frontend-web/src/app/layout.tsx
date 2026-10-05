import type { Metadata } from 'next';
import { Suspense } from 'react';
import './globals.css';
import './storefront-polish.css';
import './premium-v3.css';
import Navbar from '../components/Navbar';
import { CartProvider } from '../context/CartContext';
import CartDrawer from '../components/CartDrawer';

export const metadata: Metadata = {
  title: 'Retail Mind',
  description: 'Local commerce, reimagined.',
  manifest: '/manifest.json',
  appleWebApp: { capable: true, statusBarStyle: 'default', title: 'Retail Mind' },
};

export const viewport = {
  themeColor: '#0f5b47',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <CartProvider>
          <Navbar />
          <main className="page-transition">
            <Suspense fallback={<div className="page-loading">Loading…</div>}>{children}</Suspense>
          </main>
          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
