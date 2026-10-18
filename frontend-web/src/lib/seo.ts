import type { Metadata } from 'next';
import { API_BASE } from './api';

const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://retail-mind-1.onrender.com';

const parsedSiteUrl = new URL(configuredSiteUrl);
if (!parsedSiteUrl.hostname || parsedSiteUrl.username || parsedSiteUrl.password) {
  throw new Error('NEXT_PUBLIC_SITE_URL must be a trusted public website URL.');
}
parsedSiteUrl.protocol = 'https:';
parsedSiteUrl.pathname = '/';
parsedSiteUrl.search = '';
parsedSiteUrl.hash = '';
export const SITE_URL = parsedSiteUrl.origin;
export const SITE_NAME = 'Retail Mind';
export const FALLBACK_DESCRIPTION =
  'Discover neighbourhood shops, browse local products, and place orders with Retail Mind.';
export const FALLBACK_SOCIAL_IMAGE = '/retail-mind-social.png';
export const FALLBACK_SOCIAL_IMAGE_WIDTH = 1200;
export const FALLBACK_SOCIAL_IMAGE_HEIGHT = 630;

export function absoluteSiteUrl(path: string): string {
  return new URL(path, `${SITE_URL}/`).toString();
}

export function publicImageUrl(imageUrl?: string | null): string {
  if (!imageUrl) return absoluteSiteUrl(FALLBACK_SOCIAL_IMAGE);
  try {
    const resolved = new URL(imageUrl, `${API_BASE.replace(/\/+$/, '')}/`);
    const hasTemporaryCredentials = [...resolved.searchParams.keys()]
      .some((key) => /^(token|signature|sig|expires|x-amz-)/i.test(key));
    if (resolved.protocol !== 'https:' || hasTemporaryCredentials) {
      return absoluteSiteUrl(FALLBACK_SOCIAL_IMAGE);
    }
    resolved.username = '';
    resolved.password = '';
    return resolved.toString();
  } catch {
    return absoluteSiteUrl(FALLBACK_SOCIAL_IMAGE);
  }
}

export function publicPageMetadata({
  title,
  description,
  path,
  image,
  type = 'website',
}: {
  title: string;
  description: string;
  path: string;
  image?: string | null;
  type?: 'website' | 'article';
}): Metadata {
  const imageUrl = publicImageUrl(image);
  const isFallbackImage = imageUrl === absoluteSiteUrl(FALLBACK_SOCIAL_IMAGE);
  return {
    title: { absolute: title },
    description,
    alternates: { canonical: absoluteSiteUrl(path) },
    openGraph: {
      type,
      siteName: SITE_NAME,
      title,
      description,
      url: absoluteSiteUrl(path),
      images: [{
        url: imageUrl,
        alt: `${SITE_NAME} - ${title}`,
        ...(isFallbackImage
          ? {
              width: FALLBACK_SOCIAL_IMAGE_WIDTH,
              height: FALLBACK_SOCIAL_IMAGE_HEIGHT,
              type: 'image/png',
            }
          : {}),
      }],
    },
    twitter: {
      card: 'summary_large_image',
      title,
      description,
      images: [imageUrl],
    },
  };
}

export function serializeJsonLd(value: Record<string, unknown>): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028')
    .replace(/\u2029/g, '\\u2029');
}
