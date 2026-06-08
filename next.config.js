/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'media.valorant-api.com',
      },
      {
        protocol: 'https',
        hostname: '**.valorant-api.com',
      },
      {
        protocol: 'https',
        hostname: 'playdm.com',
      },
    ],
  },
};

module.exports = nextConfig;
