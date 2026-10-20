'use client';

import { useEffect } from 'react';

/** Register the storefront's deliberately limited static-asset cache in production. */
export default function ServiceWorkerRegister() {
  useEffect(() => {
    if (process.env.NODE_ENV !== 'production' || !('serviceWorker' in navigator)) {
      return;
    }

    navigator.serviceWorker
      .register('/retail-mind-customer-v2.js', { scope: '/' })
      .catch((error: unknown) => {
        console.error('Retail Mind service worker registration failed.', error);
      });
  }, []);

  return null;
}
