/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/store/:path*',
        destination: 'https://retail-mind-vkbp.onrender.com/store/:path*', 
      },
    ]
  },
};

export default nextConfig;
