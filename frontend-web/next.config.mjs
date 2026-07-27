import path from 'path';
import { fileURLToPath } from 'url';
import withPWAInit from 'next-pwa';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const withPWA = withPWAInit({
  dest: 'public',
  register: true,
  skipWaiting: true,
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
  // NOTE: The API proxy is removed.
  // All API calls now use absolute URLs via src/lib/api.ts
  // pointing to process.env.NEXT_PUBLIC_API_URL or the default
  // https://retail-mind-vkbp.onrender.com
};

export default withPWA(nextConfig);
