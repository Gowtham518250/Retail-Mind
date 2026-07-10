/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/store/:path*',
        destination: 'http://localhost:8000/store/:path*', 
      },
    ]
  },
};

export default nextConfig;
