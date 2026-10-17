import path from 'path';
import { fileURLToPath } from 'url';
import withSerwistInit from '@serwist/next';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const withSerwist = withSerwistInit({
  swSrc: 'src/app/sw.ts',
  swDest: 'public/retail-mind-customer-v2.js',
  swUrl: '/retail-mind-customer-v2.js',
  register: true,
  disable: process.env.NODE_ENV === 'development',
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
      { protocol: 'http', hostname: '**' },
    ],
  },
  turbopack: {
    root: path.resolve(__dirname),
  },
  // Customer web requires NEXT_PUBLIC_API_URL at build time; backend URLs are
  // environment-specific and must never silently fall back to production.
};

export default withSerwist(nextConfig);
