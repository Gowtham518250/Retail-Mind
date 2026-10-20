/* Retail Mind customer storefront service worker.
 * Only public static assets are cached. Navigations, account pages and API responses
 * remain network-only so customer-specific information is never stored in Cache Storage.
 */
const CACHE_NAME = 'retail-mind-customer-v2';
const STATIC_PREFIX = '/_next/static/';
const PUBLIC_STATIC_PREFIXES = ['/icons/', '/manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(['/manifest.json', '/icons/retail-mind.svg']);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => name.startsWith('retail-mind-customer-') && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  const isStatic = url.pathname.startsWith(STATIC_PREFIX)
    || PUBLIC_STATIC_PREFIXES.some((prefix) => url.pathname === prefix || url.pathname.startsWith(prefix));
  if (!isStatic) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;

    const response = await fetch(request);
    if (response.ok && response.type === 'basic') {
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
