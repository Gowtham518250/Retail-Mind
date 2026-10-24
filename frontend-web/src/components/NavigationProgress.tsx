'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';

export default function NavigationProgress() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  const showTimerRef = useRef<number | null>(null);
  const hideTimerRef = useRef<number | null>(null);
  const routeRef = useRef(pathname);

  useEffect(() => {
    const clearTimers = () => {
      if (showTimerRef.current !== null) window.clearTimeout(showTimerRef.current);
      if (hideTimerRef.current !== null) window.clearTimeout(hideTimerRef.current);
      showTimerRef.current = null;
      hideTimerRef.current = null;
    };

    const handleNavigation = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) return;

      const target = event.target;
      if (!(target instanceof Element)) return;
      const link = target.closest('a[href]');
      if (!(link instanceof HTMLAnchorElement)) return;
      if (link.target && link.target !== '_self') return;
      if (link.hasAttribute('download')) return;

      const destination = new URL(link.href, window.location.href);
      if (destination.origin !== window.location.origin) return;
      if (destination.pathname === window.location.pathname) return;

      clearTimers();
      showTimerRef.current = window.setTimeout(() => setVisible(true), 120);
    };

    document.addEventListener('click', handleNavigation, true);
    return () => {
      document.removeEventListener('click', handleNavigation, true);
      clearTimers();
    };
  }, []);

  useEffect(() => {
    const nextRoute = pathname;
    if (routeRef.current === nextRoute) return;
    routeRef.current = nextRoute;

    if (showTimerRef.current !== null) window.clearTimeout(showTimerRef.current);
    showTimerRef.current = null;
    if (!visible) return;
    hideTimerRef.current = window.setTimeout(() => {
      setVisible(false);
      hideTimerRef.current = null;
    }, 280);
    return () => {
      if (hideTimerRef.current !== null) window.clearTimeout(hideTimerRef.current);
    };
  }, [pathname, visible]);

  return (
    <div
      className={`navigation-progress${visible ? ' navigation-progress-visible' : ''}`}
      role="status"
      aria-live="polite"
      aria-label={visible ? 'Loading page' : undefined}
      aria-hidden={!visible}
    >
      <span />
    </div>
  );
}
