import type { Metadata } from 'next';
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
  themeColor: "#050816",
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
            {children}
          </main>
          <CartDrawer />
        </CartProvider>
      </body>
    </html>
  );
}
