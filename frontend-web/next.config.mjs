import withPWAInit from 'next-pwa';

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
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: '**',
      }
    ],
  },
  turbopack: {},
  async rewrites() {
    return [
      {
        source: '/store/:path*',
        destination: 'https://retail-mind-vkbp.onrender.com/store/:path*', 
      },
    ]
  },
};

export default withPWA(nextConfig);
