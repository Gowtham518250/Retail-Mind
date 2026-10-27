'use client';

import { useEffect } from 'react';

const TARGET = '[data-experience="marketplace"] [class*="freshArtwork"]';

/**
 * Desktop-only pointer parallax for the home hero artwork.
 * Writes --px/--py (-1..1) on the artwork; device-motion.css turns them into
 * per-layer depth. Skipped on touch devices and for reduced-motion users.
 */
export default function HeroParallax() {
  useEffect(() => {
    const mq = window.matchMedia('(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)');
    if (!mq.matches) return;

    let frame = 0;
    let el: HTMLElement | null = null;

    const onMove = (e: PointerEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        el = el && el.isConnected ? el : document.querySelector<HTMLElement>(TARGET);
        if (!el) return;
        const r = el.getBoundingClientRect();
        if (r.width === 0 || r.bottom < 0 || r.top > window.innerHeight) return;
        const px = Math.max(-1, Math.min(1, ((e.clientX - r.left) / r.width - 0.5) * 2));
        const py = Math.max(-1, Math.min(1, ((e.clientY - r.top) / r.height - 0.5) * 2));
        el.style.setProperty('--px', px.toFixed(3));
        el.style.setProperty('--py', py.toFixed(3));
      });
    };

    window.addEventListener('pointermove', onMove, { passive: true });
    return () => {
      window.removeEventListener('pointermove', onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return null;
}
