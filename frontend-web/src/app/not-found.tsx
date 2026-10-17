import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Page not found | Retail Mind',
  robots: { index: false, follow: false },
};

export default function NotFound() {
  return (
    <main className="container" style={{ minHeight: '60vh', display: 'grid', placeItems: 'center', paddingBlock: 64 }}>
      <section style={{ maxWidth: 560, textAlign: 'center' }}>
        <p className="section-eyebrow">404 · Page not found</p>
        <h1 style={{ fontSize: 'clamp(2rem, 5vw, 3.5rem)', marginBlock: 12 }}>That page isn’t on our shelves.</h1>
        <p className="muted">The link may be outdated, or the page may no longer be available.</p>
        <div style={{ display: 'flex', justifyContent: 'center', flexWrap: 'wrap', gap: 10, marginTop: 20 }}>
          <Link href="/" className="hero-cta">Back to the marketplace</Link>
          <Link href="/shops" className="store-link-btn">Browse local shops</Link>
          <Link href="/ai-shopping" className="store-link-btn">Try AI shopping</Link>
        </div>
      </section>
    </main>
  );
}
