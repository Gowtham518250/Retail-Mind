import Link from 'next/link';

export default function NotFoundContent() {
  return (
    <div className="container not-found-page">
      <section className="not-found-card" aria-labelledby="not-found-title">
        <p className="section-eyebrow">404 · Page not found</p>
        <h1 id="not-found-title">That page isn’t on our shelves.</h1>
        <p className="muted">The link may be outdated, or the page may no longer be available.</p>
        <div className="not-found-actions">
          <Link href="/" className="hero-cta">Back to the marketplace</Link>
          <Link href="/shops" className="store-link-btn">Browse local shops</Link>
          <Link href="/ai-shopping" className="store-link-btn">Try AI shopping</Link>
        </div>
      </section>
    </div>
  );
}