'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

export default function MobileWelcomeGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (pathname !== '/') return;
    try {
      const introAlreadySeen = window.localStorage.getItem('retailMindIntroSeen') === '1';
      if (!introAlreadySeen) {
        router.replace('/splash');
      }
    } catch {
      // If browser storage is unavailable, leave the customer on the marketplace.
    }
  }, [pathname, router]);

  return <>{children}</>;
}
