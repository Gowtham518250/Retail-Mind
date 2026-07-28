import { API_BASE } from './api';

/**
 * Fetches the list of known shop IDs at build time, for `generateStaticParams()`.
 * Static export (`output: 'export'`) needs every dynamic route pre-rendered for
 * a known set of params. If the backend is slow or unreachable during a build,
 * we must not hang forever — fall back to a safe default list instead.
 */
export async function getKnownShopIds(timeoutMs = 8000): Promise<string[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}/store/shops`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!res.ok) return fallbackShopIds();

    const data = await res.json();
    const shops = Array.isArray(data?.shops) ? data.shops : [];
    const ids = shops
      .map((shop: { shop_id?: number }) => (shop.shop_id ? String(shop.shop_id) : ''))
      .filter(Boolean);

    return ids.length > 0 ? ids : fallbackShopIds();
  } catch {
    return fallbackShopIds();
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Shops that must always be pre-rendered even if the build-time API call fails.
 * Add known shop IDs here (e.g. via NEXT_PUBLIC_KNOWN_SHOP_IDS="1,8,25") so
 * production builds never silently produce an empty site.
 */
function fallbackShopIds(): string[] {
  const fromEnv = process.env.NEXT_PUBLIC_KNOWN_SHOP_IDS;
  if (fromEnv) {
    return fromEnv.split(',').map((id) => id.trim()).filter(Boolean);
  }
  return ['8'];
}
