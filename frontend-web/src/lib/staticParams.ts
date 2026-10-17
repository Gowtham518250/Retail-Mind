import { API_BASE } from './api';

/**
 * Fetch known shop IDs for `generateStaticParams()`. If the backend is
 * unavailable during a build, only explicitly configured IDs are pre-rendered.
 */
export async function getKnownShopIds(timeoutMs = 8000): Promise<string[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}/store/shops`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!res.ok) return configuredShopIds();

    const data = await res.json();
    const shops = Array.isArray(data?.shops) ? data.shops : [];
    const ids = shops
      .map((shop: { shop_id?: number }) => (shop.shop_id ? String(shop.shop_id) : ''))
      .filter(Boolean);

    return ids.length > 0 ? ids : configuredShopIds();
  } catch {
    return configuredShopIds();
  } finally {
    clearTimeout(timer);
  }
}

function configuredShopIds(): string[] {
  const fromEnv = process.env.NEXT_PUBLIC_KNOWN_SHOP_IDS;
  return fromEnv
    ? fromEnv.split(',').map((id) => id.trim()).filter(Boolean)
    : [];
}
