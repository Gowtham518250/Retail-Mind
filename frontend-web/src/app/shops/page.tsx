'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, MapPin, Search, Sparkles, Star, Store } from 'lucide-react';
import { API_BASE } from '../../lib/api';
import styles from './page.module.css';

type Shop = {
  shop_id: number;
  shop_name: string;
  shop_type?: string | null;
  logo_url?: string | null;
  shop_logo_url?: string | null;
  city?: string | null;
  address?: string | null;
  tagline?: string | null;
  description?: string | null;
  rating?: number | null;
  rating_count?: number | null;
  categories?: string[] | string | null;
};
type ShopProduct = { image_url?: string | null; product_image_url?: string | null };

function assetUrl(value?: string | null) {
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return API_BASE + (value.startsWith('/') ? value : '/' + value);
}
function tagsFor(shop: Shop): string[] {
  const tags: string[] = [];
  if (shop.shop_type && shop.shop_type.trim()) tags.push(shop.shop_type.trim());
  if (Array.isArray(shop.categories)) tags.push(...shop.categories.filter((x): x is string => typeof x === 'string'));
  else if (typeof shop.categories === 'string') tags.push(...shop.categories.split(','));
  return Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean)));
}
function normalize(value: string) {
  return value.toLowerCase().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, ' ').trim();
}

function ShopCoverImage({ shop, priority }: { shop: Shop; priority: boolean }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [nearViewport, setNearViewport] = useState(priority);
  const [productImage, setProductImage] = useState('');
  const [failedImageUrl, setFailedImageUrl] = useState('');
  const logo = assetUrl(shop.logo_url || shop.shop_logo_url);

  useEffect(() => {
    if (priority) {
      setNearViewport(true);
      return;
    }
    const node = hostRef.current;
    if (!node || typeof IntersectionObserver === 'undefined') {
      setNearViewport(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setNearViewport(true);
        observer.disconnect();
      }
    }, { rootMargin: '220px 0px' });
    observer.observe(node);
    return () => observer.disconnect();
  }, [priority]);

  useEffect(() => {
    if (!nearViewport) return;
    const controller = new AbortController();
    let active = true;
    const loadProductImage = async () => {
      try {
        const response = await fetch(
          API_BASE + '/store/shops/' + encodeURIComponent(String(shop.shop_id)) + '/products',
          { cache: 'no-store', signal: controller.signal },
        );
        if (!response.ok) return;
        const detail = await response.json();
        const products: ShopProduct[] = Array.isArray(detail.products) ? detail.products : [];
        const image = products
          .map((product) => product.image_url || product.product_image_url)
          .find((value): value is string => typeof value === 'string' && value.trim().length > 0);
        if (active && image) setProductImage(assetUrl(image));
      } catch {
        // A missing product photo falls back to the shop's own logo or initials.
      }
    };
    void loadProductImage();
    return () => {
      active = false;
      controller.abort();
    };
  }, [nearViewport, shop.shop_id]);

  const image = productImage && failedImageUrl !== productImage
    ? productImage
    : logo && failedImageUrl !== logo
      ? logo
      : '';
  const usingProductImage = Boolean(image && image === productImage);

  return (
    <div className={styles.image} ref={hostRef}>
      {image ? (
        <img
          src={image}
          alt={usingProductImage ? (shop.shop_name || 'Local shop') + ' product photo' : (shop.shop_name || 'Local shop') + ' logo'}
          loading={priority ? 'eager' : 'lazy'}
          decoding="async"
          onError={() => setFailedImageUrl(image)}
        />
      ) : (
        <div className={styles.imageFallback}>
          <Store size={34} aria-hidden="true" />
          <span aria-hidden="true">{(shop.shop_name || 'S').trim().charAt(0).toUpperCase()}</span>
        </div>
      )}
      <span className={styles.categoryTag}>{shop.shop_type || tagsFor(shop)[0] || 'Local shop'}</span>
    </div>
  );
}

export default function ShopDiscoveryPage() {
  const [shops, setShops] = useState<Shop[]>([]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    const load = async () => {
      setLoading(true);
      setError('');
      try {
        const response = await fetch(
          API_BASE + '/store/marketplace/search?mode=shops&limit=60',
          { cache: 'no-store', signal: controller.signal },
        );
        if (!response.ok) throw new Error('Marketplace request failed (' + response.status + ').');
        const data = await response.json();
        const list: Shop[] = Array.isArray(data.shops) ? data.shops : [];
        setShops(list);

        // Product photography is requested lazily by each visible shop card.
      } catch (cause) {
        if (!controller.signal.aborted) {
          setShops([]);
          setError(cause instanceof Error ? cause.message : 'Unable to load local shops.');
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    };
    void load();
    return () => controller.abort();
  }, []);

  const categories = useMemo(() => {
    const values = shops.flatMap(tagsFor);
    return ['All', ...Array.from(new Set(values)).slice(0, 7)];
  }, [shops]);

  const visibleShops = useMemo(() => {
    const term = normalize(query);
    const selected = normalize(category);
    return shops.filter((shop) => {
      const searchable = normalize([
        shop.shop_name, shop.shop_type, shop.city, shop.address, shop.tagline,
        shop.description, ...tagsFor(shop),
      ].filter(Boolean).join(' '));
      const queryMatch = !term || searchable.includes(term);
      const categoryMatch = category === 'All' || tagsFor(shop).some((tag) => {
        const current = normalize(tag);
        return current.includes(selected) || selected.includes(current);
      });
      return queryMatch && categoryMatch;
    });
  }, [shops, query, category]);

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.hero}>
          <div className={styles.heroTopline}>
            <span className={styles.kicker}><Sparkles size={14} /> RETAIL MIND MARKETPLACE</span>
            <span className={styles.live}><i /> Real shop listings</span>
          </div>
          <h1>Discover Local Shops<span>.</span></h1>
          <p>Explore neighbourhood storefronts and browse the products each shop actually lists.</p>
          <label className={styles.search}>
            <Search size={19} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search shops, categories or locations"
              aria-label="Search shops, categories or locations"
            />
            {query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search">×</button>}
          </label>
          <div className={styles.trustRow}>
            <span><Store size={14} /> Shop-specific catalogues</span>
            <span><Star size={14} /> Ratings when provided</span>
            <span><MapPin size={14} /> Locations when provided</span>
          </div>
        </header>

        <section className={styles.content} aria-labelledby="shop-list-heading">
          <div className={styles.filterRow} role="group" aria-label="Filter shops by category">
            {categories.map((value) => (
              <button
                type="button"
                key={value}
                className={[styles.filter, category === value ? styles.filterActive : ''].filter(Boolean).join(' ')}
                onClick={() => setCategory(value)}
                aria-pressed={category === value}
              >
                {value}
              </button>
            ))}
          </div>

          <div className={styles.sectionHead}>
            <div>
              <span className={styles.sectionKicker}>BROWSE THE MARKETPLACE</span>
              <h2 id="shop-list-heading">Shops near your next find</h2>
              <p>Choose a shop to see its current product catalogue.</p>
            </div>
            <span className={styles.count}>{loading ? 'Loading…' : visibleShops.length + (visibleShops.length === 1 ? ' shop' : ' shops')}</span>
          </div>

          {loading ? (
            <div className={styles.grid} aria-busy="true">
              {Array.from({ length: 8 }, (_, index) => <div className={styles.skeleton} key={index} />)}
            </div>
          ) : error ? (
            <div className={styles.empty} role="alert">
              <div className={styles.emptyIcon}><Store size={23} /></div>
              <h3>Shops could not be loaded</h3>
              <p>{error}</p>
              <button type="button" className={styles.primary} onClick={() => window.location.reload()}>Try again</button>
            </div>
          ) : visibleShops.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}><Search size={23} /></div>
              <h3>No shops match that search</h3>
              <p>Try another name or choose a different category.</p>
              <button type="button" className={styles.primary} onClick={() => { setQuery(''); setCategory('All'); }}>Clear filters</button>
            </div>
          ) : (
            <div className={styles.grid}>
              {visibleShops.map((shop, index) => {
                const rating = Number(shop.rating || 0);
                const reviewCount = Number(shop.rating_count || 0);
                return (
                  <Link href={'/shop/' + shop.shop_id} className={styles.card} key={shop.shop_id}>
                    <ShopCoverImage shop={shop} priority={index < 4} />
                    <div className={styles.cardBody}>
                      <div className={styles.cardMeta}>
                        <span><Star size={13} fill={rating > 0 ? 'currentColor' : 'none'} /> {rating > 0 && reviewCount > 0 ? rating.toFixed(1) : 'New'}{reviewCount > 0 ? ' · ' + reviewCount + ' reviews' : ''}</span>
                        <ArrowRight size={15} />
                      </div>
                      <h3>{shop.shop_name || 'Local shop'}</h3>
                      <p className={styles.location}><MapPin size={13} /> {shop.city || shop.address || 'Location not provided'}</p>
                      <p className={styles.description}>{shop.tagline || shop.description || 'Open this storefront to view its current products and shop details.'}</p>
                      <span className={styles.visit}>Visit storefront <ArrowRight size={15} /></span>
                    </div>
                  </Link>
                );
              })}
            </div>
          )}
        </section>

        <footer className={styles.footer}>
          <Link href="/">Retail Mind <span>· Back to marketplace</span></Link>
          <span>Shop details and availability are shown as provided by each shop.</span>
        </footer>
      </div>
    </main>
  );
}
