import type { Metadata } from 'next';
import { Suspense } from 'react';
import './globals.css';
import Navbar from '../components/Navbar';
import { CartProvider } from '../context/CartContext';
import CartDrawer from '../components/CartDrawer';

export const metadata: Metadata = {
  title: "RetailShop",
  description: "Your ultimate shopping destination",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "RetailShop",
  },
};

export const viewport = {
  themeColor: '#050816',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <CartProvider>
          <Navbar />
          <main className="page-transition">
            <Suspense fallback={<div className="page-loading">Loading...</div>}>
              {children}
            </Suspense>
          </main>
          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
