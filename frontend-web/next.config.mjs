import path from 'path';
import { fileURLToPath } from 'url';
import withPWAInit from 'next-pwa';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const withPWA = withPWAInit({
  dest: 'public',
  // Use a versioned worker URL so browsers replace a previously cached storefront worker.
  sw: 'retail-mind-customer-v2.js',
  cacheId: 'retail-mind-customer-v2',
  register: true,
  skipWaiting: true,
  clientsClaim: true,
  cleanupOutdatedCaches: true,
  disable: process.env.NODE_ENV === 'development',
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
      { protocol: 'http',  hostname: '**' },
    ],
  },
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Customer web requires NEXT_PUBLIC_API_URL at build time; backend URLs are
  // environment-specific and must never silently fall back to production.

};

export default withPWA(nextConfig);
