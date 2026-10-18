'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import dynamic from 'next/dynamic';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { ArrowRight, ArrowUpRight, Bot, Boxes, Croissant, Flower2, MapPin, Search, ShoppingBasket, Sparkles, Star, Store } from 'lucide-react';
import styles from './Home.module.css';
import { API_BASE } from '../lib/api';
import { trackEvent } from '../lib/analytics';
import type { PublicProductPreview, PublicShop } from '../lib/publicCatalog';
import Tilt3D from './Tilt3D';

// WebGL is client-only and heavy: load it after first paint.
const HeroScene3D = dynamic(() => import('./HeroScene3D'), { ssr: false });

const EASE = [0.2, 0.75, 0.25, 1] as const;

// Deterministic colourways so every shop gets its own identity.
const SHOP_TONES = [
  ['#f3ca4f', '#e8541e', '#182820'],
  ['#cfe3c6', '#2b4436', '#fbf6ec'],
  ['#ffd9c7', '#e8541e', '#fff'],
  ['#e7dcc2', '#8a6a2f', '#fbf6ec'],
  ['#d7e6f0', '#2b4436', '#fbf6ec'],
];

const resolveLogo = (url?: string) => (url ? (url.startsWith('http') ? url : API_BASE + url) : '');

function Words({ text, base = 0, className }: { text: string; base?: number; className?: string }) {
  const reduceMotion = Boolean(useReducedMotion());
  return (
    <>
      {text.split(' ').map((word, i) => (
        <span key={i + word}><span className={styles.wordMask}>
          <motion.span
            className={`${styles.word} ${className || ''}`}
            initial={false}
            animate={{ y: 0, rotate: 0 }}
            transition={{ duration: 0 }}
          >
            {word}
          </motion.span>
        </span>{' '}</span>
      ))}
    </>
  );
}

function Reveal({ children, delay = 0, className }: { children: React.ReactNode; delay?: number; className?: string }) {
  const reduceMotion = Boolean(useReducedMotion());
  return (
    <motion.div
      className={className}
      initial={false}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-70px' }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.7, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

function ShopCard({ shop, index }: { shop: any; index: number }) {
  const reduceMotion = Boolean(useReducedMotion());
  const [from, to, ink] = SHOP_TONES[Math.abs(Number(shop.shop_id) || index) % SHOP_TONES.length];
  const logo = resolveLogo(shop.logo_url);
  const rated = Boolean(shop.rating_count);
  return (
    <motion.div
      initial={false}
      whileInView={{ opacity: 1, y: 0, rotateX: 0 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={reduceMotion ? { duration: 0 } : { duration: 0.65, delay: (index % 4) * 0.08, ease: EASE }}
      style={{ transformPerspective: 1100 }}
    >
      <Tilt3D className={styles.tiltFill}>
        <Link href={'/shop/' + shop.shop_id} className={styles.shopCard}>
          <div className={styles.shopVisual} style={{ background: `linear-gradient(135deg, ${from}, ${to})`, color: ink }}>
            <span className={styles.shopInitial} aria-hidden="true">{(shop.shop_name || 'S').trim().charAt(0).toUpperCase()}</span>
            <span className={styles.liveTag}><i /> Online</span>
            <div className={styles.shopTile}>
              {logo ? <Image src={logo} alt={shop.shop_name + ' logo'} width={64} height={64} sizes="64px" loading="lazy" decoding="async" /> : <Store size={34} strokeWidth={1.6} />}
            </div>
            <span className={styles.shopOrbOne} aria-hidden="true" />
            <span className={styles.shopOrbTwo} aria-hidden="true" />
          </div>
          <div className={styles.shopBody}>
            <div className={styles.shopTopline}>
              <span>{shop.shop_type || 'Neighbourhood store'}</span>
              <b><Star size={12} fill="currentColor" /> {rated ? Number(shop.rating || 0).toFixed(1) : 'New'}</b>
            </div>
            <strong className={styles.shopName}>{shop.shop_name}</strong>
            <span className={styles.shopLoc}><MapPin size={13} /> {shop.city || shop.address || 'Local delivery'}</span>
            <p>{shop.tagline || shop.description || 'A local favourite, ready when you are.'}</p>
            <div className={styles.shopFoot}>
              <span>{shop.rating_count || 0} {Number(shop.rating_count || 0) === 1 ? 'review' : 'reviews'}</span>
              <span className={styles.shopGo}>Visit <ArrowUpRight size={15} /></span>
            </div>
          </div>
        </Link>
      </Tilt3D>
    </motion.div>
  );
}

function ProductRow({ href, rank, title, shop, meta, price, icon }: { href: string; rank?: number; title: string; shop: string; meta: React.ReactNode; price: number; icon?: boolean }) {
  return (
    <Link href={href} className={styles.row}>
      <span className={styles.rowMark}>{icon ? <Boxes size={18} /> : rank}</span>
      <div className={styles.rowMain}>
        <strong>{title}</strong>
        <span>{shop}</span>
        <small>{meta}</small>
      </div>
      <div className={styles.rowPrice}>₹{Number(price || 0).toFixed(2)}</div>
      <ArrowUpRight size={16} className={styles.rowArrow} />
    </Link>
  );
}

type ResultMode = 'all' | 'shops' | 'products';

type FeaturedProduct = { product_id: number; product_name: string; shop_id: number; shop_name: string; price: number; image_url?: string | null; category?: string; description?: string; stock_available?: number };

export default function MarketplaceShell({
  initialShops = [],
  initialFeaturedProducts = [],
}: {
  initialShops?: PublicShop[];
  initialFeaturedProducts?: PublicProductPreview[];
}) {
  const router = useRouter();
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>(initialFeaturedProducts.length ? 'products' : 'shops');
  const [shops, setShops] = useState<PublicShop[]>(initialShops);
  const [products, setProducts] = useState<any[]>([]);
  const [featuredProducts, setFeaturedProducts] = useState<FeaturedProduct[]>(initialFeaturedProducts);
  const [activeProductCategory, setActiveProductCategory] = useState('All');
  const [aiMessage, setAiMessage] = useState('');
  const [aiResults, setAiResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);
  const skipInitialFeaturedLoad = useRef(initialShops.length > 0);

  const showcaseProducts = useMemo<FeaturedProduct[]>(() => {
    // When the customer searches specifically for products, showcase those actual
    // results. Otherwise use the cross-shop featured product feed.
    const source: any[] = mode === 'products' && query.trim() && products.length
      ? products
      : featuredProducts;
    return source.map((product: any) => ({
      product_id: Number(product.product_id ?? product.id),
      product_name: String(product.product_name ?? product.name ?? 'Product'),
      shop_id: Number(product.shop_id),
      shop_name: String(product.shop_name ?? 'Local shop'),
      price: Number(product.price ?? product.unit_price ?? 0),
      image_url: typeof product.image_url === 'string' ? product.image_url : null,
      category: String(product.category ?? '').trim(),
      description: String(product.description ?? ''),
      stock_available: Number(product.stock_available ?? product.current_stock ?? 0),
    })).filter((product) => Number.isFinite(product.product_id) && product.product_id > 0);
  }, [mode, query, products, featuredProducts]);

  const productCategories = useMemo(() => {
    const values = showcaseProducts
      .map((product) => (product.category || '').trim())
      .filter((category) => category.length > 0);
    return ['All', ...Array.from(new Set(values)).slice(0, 6)];
  }, [showcaseProducts]);

  const filteredFeaturedProducts = useMemo(() => {
    if (activeProductCategory === 'All') return showcaseProducts;
    return showcaseProducts.filter((product) => product.category === activeProductCategory);
  }, [activeProductCategory, showcaseProducts]);

  const discoveryCategories = useMemo(() => {
    const values: string[] = [];
    shops.forEach((shop) => {
      if (typeof shop.shop_type === 'string' && shop.shop_type.trim()) values.push(shop.shop_type.trim());
      const listed = Array.isArray(shop.categories)
        ? shop.categories
        : typeof shop.categories === 'string'
          ? shop.categories.split(',')
          : [];
      listed.forEach((item: unknown) => {
        if (typeof item === 'string' && item.trim()) values.push(item.trim());
      });
    });
    const cleaned = Array.from(new Set(values)).filter((value) => !/^(general|local store|online)$/i.test(value));
    return (cleaned.length ? cleaned : ['Groceries', 'Bakery', 'Personal care']).slice(0, 5);
  }, [shops]);

  const performSearch = async (requestedMode: ResultMode, requestedQuery: string, userInitiated = false) => {
    const value = requestedQuery.trim();
    const requestId = ++requestIdRef.current;
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;

    setLoading(true);
    setError('');
    setAiResults([]);
    setAiMessage('');
    if (userInitiated) setSearching(true);

    try {
      if (!value) {
        const res = await fetch('/api/marketplace/search?mode=shops&limit=60', { cache: 'no-store', signal: controller.signal });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Marketplace API returned ' + res.status + '.');
        if (requestId !== requestIdRef.current) return;
        setShops(Array.isArray(data.shops) ? data.shops : []);
        setProducts([]);
        return;
      }

      const searchMode = requestedMode === 'shops' ? 'shops' : requestedMode === 'products' ? 'products' : 'all';
      const res = await fetch(
        '/api/marketplace/search?q=' + encodeURIComponent(value) + '&mode=' + searchMode + '&limit=30',
        { cache: 'no-store', signal: controller.signal }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Marketplace API returned ' + res.status + '.');
      if (requestId !== requestIdRef.current) return;

      setShops(Array.isArray(data.shops) ? data.shops : []);
      setProducts(Array.isArray(data.products) ? data.products : []);
      if (userInitiated && value) {
        trackEvent('search', {
          search_term: value,
          search_scope: requestedMode,
          result_count: (Array.isArray(data.shops) ? data.shops.length : 0)
            + (Array.isArray(data.products) ? data.products.length : 0),
        });
      }
    } catch (err) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setShops([]);
      setProducts([]);
      setError(err instanceof TypeError
        ? 'We couldn’t reach the marketplace. Check your connection and try again.'
        : err instanceof Error
          ? err.message
          : 'Unable to search the marketplace.');
    } finally {
      if (requestId === requestIdRef.current) {
        setLoading(false);
        setSearching(false);
      }
    }
  };

  const performAiSearch = async () => {
    const value = query.trim();
    if (!value) {
      router.push('/ai-shopping');
      return;
    }
    setSearching(true);
    setError('');
    try {
      const res = await fetch(API_BASE + '/store/ai/recommend?q=' + encodeURIComponent(value) + '&limit=10', { cache: 'no-store' });
      if (!res.ok) throw new Error('Shopping API returned ' + res.status + '.');
      const data = await res.json();
      setAiResults(Array.isArray(data.recommendations) ? data.recommendations : []);
      setAiMessage(data.response || '');
      setShops([]);
      setProducts([]);
      trackEvent('ai_search', {
        search_term: value,
        result_count: Array.isArray(data.recommendations) ? data.recommendations.length : 0,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to ask the shopping assistant.');
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    const sections = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal-section]'));
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduceMotion && 'IntersectionObserver' in window) {
      sections.forEach((section) => section.classList.add(styles.revealPending));
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add(styles.revealVisible);
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -35px 0px' });
      sections.forEach((section) => observer.observe(section));
      return () => observer.disconnect();
    }
  }, []);

  useEffect(() => {
    if (skipInitialFeaturedLoad.current) {
      skipInitialFeaturedLoad.current = false;
      return;
    }
    let cancelled = false;
    const visibleShops = shops.slice(0, 6);
    if (!visibleShops.length) {
      setFeaturedProducts([]);
      return () => { cancelled = true; };
    }
    const loadFeaturedProducts = async () => {
      const batches = await Promise.all(visibleShops.map(async (shop) => {
        try {
          const response = await fetch('/api/marketplace/shops/' + encodeURIComponent(String(shop.shop_id)) + '/products', { cache: 'no-store' });
          if (!response.ok) return [];
          const data = await response.json();
          const list = Array.isArray(data.products) ? data.products : [];
          return list.map((product: any) => ({
            product_id: Number(product.id ?? product.product_id),
            product_name: String(product.name ?? product.product_name ?? 'Product'),
            shop_id: Number(shop.shop_id),
            shop_name: String(data.shop_name ?? shop.shop_name ?? 'Local shop'),
            price: Number(product.price ?? product.unit_price ?? 0),
            image_url: typeof product.image_url === 'string' ? product.image_url : null,
            category: String(product.category ?? '').trim(),
            description: String(product.description ?? ''),
            stock_available: Number(product.stock_available ?? product.current_stock ?? 0),
          })).filter((product: FeaturedProduct) =>
            Number.isFinite(product.product_id) && product.product_id > 0 && product.product_name !== 'Product'
          );
        } catch {
          return [];
        }
      }));
      if (!cancelled) {
        const seen = new Set<string>();
        const combined = batches.flat().filter((product) => {
          const key = product.shop_id + ':' + product.product_id;
          if (seen.has(key)) return false;
          seen.add(key);
          return true;
        });
        setFeaturedProducts(combined.slice(0, 16));
      }
    };
    void loadFeaturedProducts();
    return () => { cancelled = true; };
  }, [shops]);

  useEffect(() => () => {
    requestIdRef.current += 1;
    controllerRef.current?.abort();
  }, []);

  const resultsRef = useRef<HTMLElement>(null);
  const scrollToResults = () => {
    resultsRef.current?.scrollIntoView({ behavior: shouldReduceMotion ? 'auto' : 'smooth', block: 'start' });
  };

  const preset = (value: string) => {
    setActiveProductCategory('All');
    setQuery(value);
    setMode('all');
    void performSearch('all', value, true);
    scrollToResults();
  };


  const heroRef = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ['start start', 'end start'] });
  const copyY = useTransform(scrollYProgress, [0, 1], [0, 70]);
  const copyOpacity = useTransform(scrollYProgress, [0, 0.8], [1, 0.2]);

  const searchModes: { id: ResultMode; label: string; icon?: React.ReactNode }[] = [
    { id: 'products', label: 'Products', icon: <Boxes size={14} /> },
    { id: 'shops', label: 'Shops', icon: <Store size={14} /> },
    { id: 'all', label: 'Everything' },
  ];

  const submitSearch = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void performSearch(mode, query, true);
    scrollToResults();
  };

  return (
    <div className={styles.page} data-experience="marketplace">
      {/* ───────── HERO ───────── */}
      <section className={styles.hero} ref={heroRef}>
        <div className={styles.heroBg} aria-hidden="true" />
        <div className={styles.heroGrain} aria-hidden="true" />

        <motion.div className={styles.heroCopy} style={{ y: shouldReduceMotion ? 0 : copyY, opacity: shouldReduceMotion ? 1 : copyOpacity }}>
          <h1 className={styles.title}>
            <span className={styles.titleLine}><Words text="Shop local." base={0.1} /></span>
            <span className={styles.titleLine}><Words text="Find it faster." base={0.35} className={styles.titleAccent} /></span>
          </h1>

          <motion.p className={styles.lead} initial={false} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.9, ease: EASE }}>
            Search local products and compare prices.
          </motion.p>

          <motion.div initial={false} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 1.05, ease: EASE }}>
            <form className={styles.search} onSubmit={submitSearch} role="search" aria-label="Search local products">
              <Search size={20} className={styles.searchIcon} />
              <input
                type="search"
                inputMode="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search products, e.g. milk or bread"
                aria-label="Search products in local shops"
              />
              <button type="submit" disabled={searching}>
                {searching ? 'Searching…' : 'Search'} <ArrowRight size={16} />
              </button>
            </form>

            <div className={styles.modes} role="group" aria-label="Search scope">
              {searchModes.map((m) => (
                <button
                  type="button"
                  key={m.id}
                  className={mode === m.id ? styles.modeOn : styles.mode}
                  aria-pressed={mode === m.id}
                  onClick={() => { setMode(m.id); void performSearch(m.id, query, true); }}
                >
                  {mode === m.id && <motion.span layoutId="modePill" className={styles.modePill} transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
                  <span className={styles.modeLabel}>{m.icon}{m.label}</span>
                </button>
              ))}
              <button type="button" className={styles.modeAi} onClick={performAiSearch}><Bot size={14} /> Ask AI</button>
            </div>
            <div className={styles.quickSearches} aria-label="Popular searches">
              <span>Popular:</span>
              {[
                { label: 'Groceries', icon: <ShoppingBasket size={15} /> },
                { label: 'Bakery', icon: <Croissant size={15} /> },
                { label: 'Personal care', icon: <Flower2 size={15} /> },
              ].map((item) => (
                <button key={item.label} type="button" onClick={() => preset(item.label)}>
                  {item.icon}{item.label}
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>

        <div className={styles.stage}>
          <div className={styles.stageGlow} aria-hidden="true" />
          <HeroScene3D className={styles.canvas} />
        </div>
      </section>

      {error && (
        <section className={styles.section}>
          <div className={styles.banner} role="alert">
            <span className={styles.bannerIcon}>!</span>
            <div><strong>Marketplace connection issue</strong><p>{error}</p></div>
            <button
              type="button"
              className={styles.bannerRetry}
              onClick={() => void performSearch(mode, query, true)}
              disabled={searching}
            >
              {searching ? 'Retrying…' : 'Try again'}
            </button>
          </div>
        </section>
      )}
      {aiMessage && (
        <section className={styles.section}>
          <div className={`${styles.banner} ${styles.bannerAi}`}>
            <span className={styles.bannerIcon}><Sparkles size={17} /></span>
            <div><strong>Retail Mind AI</strong><p>{aiMessage}</p></div>
          </div>
        </section>
      )}

      {/* ───────── RESULTS ───────── */}
      <section className={`${styles.section} ${styles.results}`} id="shops" ref={resultsRef}>
        {loading ? (
          <>
            <div className={styles.head}><div><div className={styles.kicker}>Discover</div><h2 className={styles.h2}>Loading local products</h2></div></div>
            <div className={styles.grid}>{Array.from({ length: 8 }).map((_, i) => <div className={styles.skeleton} key={i} />)}</div>
          </>
        ) : aiResults.length ? (
          <>
            <div className={styles.head}><div><div className={styles.kicker}>AI curated</div><h2 className={styles.h2}>Recommended for you</h2></div><span className={styles.count}>{aiResults.length} picks</span></div>
            <div className={styles.list}>
              {aiResults.map((item, index) => (
                <Reveal key={String(item.product_id) + '-' + String(item.shop_id) + '-' + String(index)} delay={index * 0.04}>
                  <ProductRow
                    href={'/shop/' + item.shop_id}
                    rank={index + 1}
                    title={item.product_name}
                    shop={item.shop_name}
                    price={item.price}
                    meta={<><Star size={12} fill="currentColor" /> {item.rating_count ? item.rating : 'New'} · {item.rating_count || 0} reviews</>}
                  />
                </Reveal>
              ))}
            </div>
          </>
        ) : error ? (
          <div className={styles.empty} role="status">
            <span><Search size={24} /></span>
            <strong>Marketplace results are temporarily unavailable</strong>
            <p>We couldn’t load shops or products. Use “Try again” above to refresh.</p>
          </div>
        ) : query.trim() ? (
          <>
            <div className={styles.head}>
              <div>
                <div className={styles.kicker}>Results</div>
                <h2 className={styles.h2}>{mode === 'shops' ? 'Shops' : mode === 'products' ? 'Products' : 'Matches'}</h2>
              </div>
            </div>

            {mode !== 'products' && shops.length > 0 && (
              <div className={styles.grid}>{shops.map((shop, i) => <ShopCard key={shop.shop_id} shop={shop} index={i} />)}</div>
            )}

            {mode !== 'shops' && products.length > 0 && (
              <div className={styles.list}>
                {products.map((product, i) => (
                  <Reveal key={String(product.product_id) + '-' + String(product.shop_id)} delay={Math.min(i, 8) * 0.03}>
                    <ProductRow
                      href={'/shop/' + product.shop_id + '/product/' + product.product_id}
                      icon
                      title={product.product_name}
                      shop={product.shop_name}
                      price={product.price}
                      meta={<><Star size={12} fill="currentColor" /> {product.rating_count ? product.rating : 'New'} · {product.stock_available > 0 ? 'In stock' : 'Out of stock'}</>}
                    />
                  </Reveal>
                ))}
              </div>
            )}

            {!shops.length && !products.length && (
              <div className={styles.empty}>
                <span><Search size={24} /></span>
                <strong>{mode === 'products' ? 'No products match yet' : mode === 'shops' ? 'No shops match yet' : 'No matches yet'}</strong>
                <p>{mode === 'products'
                  ? 'Try another product name, or choose Shops to browse local stores.'
                  : 'Try a broader shop, category or product keyword.'}</p>
              </div>
            )}
          </>
        ) : mode === 'products' ? (
          <>
            <div className={styles.head}>
              <div>
                <div className={styles.kicker}><Boxes size={12} /> Shop local products</div>
                <h2 className={styles.h2}>Popular products nearby</h2>
              </div>
              <span className={styles.count}>{showcaseProducts.length} {showcaseProducts.length === 1 ? 'product' : 'products'}</span>
            </div>
            {filteredFeaturedProducts.length ? (
              <div className={styles.list}>
                {filteredFeaturedProducts.map((product, index) => (
                  <Reveal key={`${product.shop_id}-${product.product_id}`} delay={Math.min(index, 8) * 0.03}>
                    <ProductRow
                      href={'/shop/' + product.shop_id + '/product/' + product.product_id}
                      icon
                      title={product.product_name}
                      shop={product.shop_name}
                      price={product.price}
                      meta={<>{Number(product.stock_available ?? 0) > 0 ? 'In stock' : 'Check availability'}{product.category ? ' · ' + product.category : ''}</>}
                    />
                  </Reveal>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>
                <span><Boxes size={24} /></span>
                <strong>No products are listed yet</strong>
                <p>Browse local shops now, or check back as stores add their products.</p>
                <button
                  type="button"
                  className={styles.emptyRetry}
                  onClick={() => { setMode('shops'); void performSearch('shops', '', true); }}
                >
                  Browse shops
                </button>
              </div>
            )}
          </>
        ) : (
          <>
            <div className={styles.head}>
              <div>
                <div className={styles.kicker}><Sparkles size={12} /> Local storefronts</div>
                <h2 className={styles.h2}>Find your next favourite shop</h2>
              </div>
              <span className={styles.count}>{shops.length} {shops.length === 1 ? 'shop' : 'shops'}</span>
            </div>
            <div className={styles.grid}>{shops.map((shop, i) => <ShopCard key={shop.shop_id} shop={shop} index={i} />)}</div>
            {!shops.length && (
              <div className={styles.empty} role="status">
                <span><Store size={24} /></span>
                <strong>No online shops are showing right now</strong>
                <p>There are no shops available to browse yet. Check again in a moment.</p>
                <button
                  type="button"
                  className={styles.emptyRetry}
                  onClick={() => void performSearch('shops', '', true)}
                  disabled={searching}
                >
                  {searching ? 'Checking shops…' : 'Refresh shops'}
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
