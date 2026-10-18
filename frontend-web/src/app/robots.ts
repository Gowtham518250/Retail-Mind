import type { MetadataRoute } from 'next';
import { absoluteSiteUrl, SITE_URL } from '../lib/seo';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/auth',
          '/orders',
          '/profile',
          '/smart-shop',
          '/api/',
          '/shop/*/checkout',
          '/shop/*/order-success',
        ],
      },
    ],
    sitemap: absoluteSiteUrl('/sitemap.xml'),
    host: SITE_URL,
  };
}
