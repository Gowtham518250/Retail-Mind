'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, ArrowUpRight, Boxes, Croissant, MapPin, Search, ShoppingBasket, ShieldCheck, Sparkles, Star, Store, Truck, Zap, Apple, Milk, Coffee, Leaf, Plus, ShoppingCart, UserRound, ChevronRight, CheckCircle2 } from 'lucide-react';
import styles from './Home.module.css';
import { API_BASE } from '../lib/api';
import Tilt3D from './Tilt3D';
import { useCart } from '../context/CartContext';
import type { PublicProductPreview, PublicShop } from '../lib/publicCatalog';

const EASE = [0.2, 0.75, 0.25, 1] as const;

// Deterministic colourways so every shop gets its own identity.
const SHOP_TONES = [
  ['#e9efff', '#cddcff', '#142857'],
  ['#e3faf4', '#bfeee1', '#17483e'],
  ['#f0edff', '#d9d3ff', '#2b255f'],
  ['#fff4df', '#ffe0ad', '#654b13'],
  ['#e7f6ff', '#c8eaff', '#163d5f'],
];

const resolveLogo = (url?: string) => (url ? (url.startsWith('http') ? url : API_BASE + url) : '');

function ShopCard({ shop, index }: { shop: any; index: number }) {
  const reduceMotion = Boolean(useReducedMotion());
  const [from, to, ink] = SHOP_TONES[Math.abs(Number(shop.shop_id) || index) % SHOP_TONES.length];
  const logo = resolveLogo(shop.logo_url);
  const rated = Boolean(shop.rating_count);
  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 40, rotateX: -8 }}
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
              {logo ? <img src={logo} alt={shop.shop_name + ' logo'} width={64} height={64} loading="lazy" decoding="async" /> : <Store size={34} strokeWidth={1.6} />}
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

type ResultMode = 'all' | 'shops' | 'products';

type FeaturedProduct = { product_id: number; product_name: string; shop_id: number; shop_name: string; price: number; image_url?: string | null; category?: string; description?: string; stock_available?: number };

type MarketplaceShellProps = {
  initialShops: PublicShop[];
  initialFeaturedProducts: PublicProductPreview[];
};

export default function MarketplaceShell({
  initialShops,
  initialFeaturedProducts,
}: MarketplaceShellProps) {
  const router = useRouter();
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>('all');
  const [shops, setShops] = useState<any[]>(initialShops);
  const [products, setProducts] = useState<any[]>([]);
  const [featuredProducts, setFeaturedProducts] = useState<FeaturedProduct[]>(initialFeaturedProducts);
  const [activeProductCategory, setActiveProductCategory] = useState('All');
  const [aiMessage, setAiMessage] = useState('');
  const [aiResults, setAiResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(initialShops.length === 0);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  const showcaseProducts = useMemo<FeaturedProduct[]>(() => {
    // When the customer searches specifically for products, showcase those actual
    // results. Otherwise use the cross-shop featured product feed.
    const source: any[] = query.trim() && mode !== 'shops' && products.length
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
      stock_available: product.stock_available == null && product.current_stock == null ? undefined : Number(product.stock_available ?? product.current_stock),
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
            stock_available: product.stock_available == null && product.current_stock == null ? undefined : Number(product.stock_available ?? product.current_stock),
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

  useEffect(() => {
    if (initialShops.length > 0) {
      setLoading(false);
      return () => {
        requestIdRef.current += 1;
        controllerRef.current?.abort();
      };
    }
    void performSearch('all', '');
    return () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  const preset = (value: string) => {
    setActiveProductCategory('All');
    setQuery(value);
    // These chips come from real shop categories/types, so search both shops and products.
    setMode('all');
    void performSearch('all', value, true);
  };


  const { addToCart, itemCount, toggleCart } = useCart();

  const searchModes: { id: ResultMode; label: string; icon?: React.ReactNode }[] = [
    { id: 'all', label: 'All' },
    { id: 'shops', label: 'Shops', icon: <Store size={14} /> },
    { id: 'products', label: 'Products', icon: <Boxes size={14} /> },
  ];

  const categories = [
    { label: 'All', icon: <Boxes size={22} />, tone: 'purple' },
    { label: 'Groceries', icon: <ShoppingBasket size={22} />, tone: 'blue' },
    { label: 'Snacks', icon: <Croissant size={22} />, tone: 'peach' },
    { label: 'Beverages', icon: <Coffee size={22} />, tone: 'purple' },
    { label: 'Fruits', icon: <Apple size={22} />, tone: 'pink' },
    { label: 'Vegetables', icon: <Leaf size={22} />, tone: 'green' },
    { label: 'Dairy', icon: <Milk size={22} />, tone: 'yellow' },
  ];

  const addProduct = (product: FeaturedProduct) => {
    const image = product.image_url ? resolveLogo(product.image_url) : undefined;
    addToCart({
      id: product.product_id,
      name: product.product_name,
      price: product.price,
      description: product.description,
      stock_available: product.stock_available,
      category: product.category,
      image_url: image,
      shop_id: product.shop_id,
    });
  };

  return (
    <div className={styles.page} data-experience="marketplace">
      <div className={styles.marketHeader}>
        <div className={styles.locationGroup}>
          <span className={styles.locationIcon}><MapPin size={16} /></span>
          <span className={styles.locationCopy}>
            <small>DELIVER TO</small>
            <strong>Kadapa, Andhra Pradesh</strong>
          </span>
        </div>
        <div className={styles.headerActions}>
          <Link href="/profile" className={styles.accountButton} aria-label="My profile">
            <UserRound size={18} />
          </Link>
          <button type="button" className={styles.headerCart} onClick={toggleCart} aria-label={'Open cart, ' + itemCount + ' items'}>
            <ShoppingCart size={18} />
            <span>Cart</span>
            {itemCount > 0 && <b>{itemCount}</b>}
          </button>
        </div>
      </div>

      <div className={styles.marketContent}>
        <form
          className={styles.marketSearch}
          role="search"
          onSubmit={(event) => { event.preventDefault(); void performSearch(mode, query, true); }}
        >
          <Search size={19} className={styles.marketSearchIcon} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search for products or shops..."
            aria-label="Search for products or shops"
          />
          <button type="submit" aria-label="Search marketplace" disabled={searching}>
            <Search size={18} />
          </button>
        </form>

        <section className={styles.freshBanner} aria-labelledby="fresh-banner-title">
          <div className={styles.freshBannerCopy}>
            <span className={styles.freshBadge}><CheckCircle2 size={13} /> Fresh & local</span>
            <h1 id="fresh-banner-title">Fresh products<br /><span>from local shops.</span></h1>
            <p>Fast · Reliable · Nearby</p>
            <button type="button" className={styles.freshCta} onClick={() => { setMode('shops'); void performSearch('shops', '', true); }}>
              Start shopping <ArrowRight size={16} />
            </button>
          </div>
          <div className={styles.freshArtwork} aria-hidden="true">
            <span className={styles.artHalo} />
            <span className={styles.artTile + ' ' + styles.artTileOne}><Apple size={36} /></span>
            <span className={styles.artTile + ' ' + styles.artTileTwo}><Milk size={34} /></span>
            <span className={styles.artTile + ' ' + styles.artTileThree}><Leaf size={35} /></span>
            <span className={styles.artBasket}><ShoppingBasket size={82} strokeWidth={1.5} /></span>
          </div>
        </section>

        {error && (
          <div className={styles.connectionNotice} role="alert">
            <span className={styles.noticeIcon}><Zap size={17} /></span>
            <div><strong>Marketplace connection issue</strong><p>{error}</p></div>
            <button type="button" onClick={() => void performSearch(mode, query, true)} disabled={searching}>
              {searching ? 'Retrying…' : 'Retry'}
            </button>
          </div>
        )}

        {aiMessage && (
          <div className={styles.aiNotice}>
            <span className={styles.noticeIcon}><Sparkles size={17} /></span>
            <div><strong>Retail Mind AI</strong><p>{aiMessage}</p></div>
          </div>
        )}

        <section className={styles.marketSection} id="categories" aria-label="Shop by category">
          <div className={styles.categoryGrid}>
            {categories.map((category) => (
              <button
                key={category.label}
                type="button"
                className={styles.categoryButton}
                onClick={() => {
                  setActiveProductCategory('All');
                  if (category.label === 'All') {
                    setQuery('');
                    setMode('all');
                    void performSearch('all', '', true);
                  } else {
                    preset(category.label);
                  }
                }}
              >
                <span className={styles.categoryIcon + ' ' + styles['category' + category.tone]}>
                  {category.icon}
                </span>
                <span>{category.label}</span>
              </button>
            ))}
          </div>
        </section>

        <section className={styles.marketSection} id="shops" aria-labelledby="shops-heading">
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>{query.trim() ? 'YOUR SEARCH' : 'GOOD STORES, CLOSE TO HOME'}</span>
              <h2 id="shops-heading">{query.trim() ? (mode === 'shops' ? 'Shops matching your search' : 'Search results') : 'Nearby shops'}</h2>
              <p>{query.trim() ? 'Explore matching local stores and the products they offer.' : 'Discover neighbourhood stores ready for your next order.'}</p>
            </div>
            <Link href="/shops" className={styles.viewAllLink}>View all <ChevronRight size={16} /></Link>
          </div>

          {loading ? (
            <div className={styles.shopsGrid}>
              {Array.from({ length: 3 }).map((_, index) => <div className={styles.marketSkeleton} key={index} />)}
            </div>
          ) : shops.length ? (
            <div className={styles.shopsGrid}>
              {shops.slice(0, query.trim() ? 12 : 6).map((shop, index) => <ShopCard key={shop.shop_id} shop={shop} index={index} />)}
            </div>
          ) : (
            <div className={styles.emptyMarketplace}>
              <span><Store size={26} /></span>
              <strong>{error ? 'Shops are temporarily unavailable' : 'No online shops to show yet'}</strong>
              <p>{error ? 'Check your connection and try again.' : 'Please check back soon, or search for another category.'}</p>
              <button type="button" onClick={() => void performSearch('shops', '', true)} disabled={searching}>
                {searching ? 'Checking…' : 'Refresh shops'}
              </button>
            </div>
          )}
        </section>

        {aiResults.length > 0 && (
          <section className={styles.marketSection} aria-labelledby="ai-results-heading">
            <div className={styles.sectionHeader}>
              <div><span className={styles.sectionEyebrow}>PERSONALISED PICKS</span><h2 id="ai-results-heading">Recommended for you</h2></div>
            </div>
            <div className={styles.productGrid}>
              {aiResults.map((item, index) => (
                <article className={styles.productCard} key={String(item.product_id) + '-' + String(item.shop_id) + '-' + String(index)}>
                  <div className={styles.productPicture}><ShoppingBasket size={34} /></div>
                  <div className={styles.productCardBody}>
                    <small>{item.shop_name || 'Local shop'}</small>
                    <strong>{item.product_name}</strong>
                    <div className={styles.productCardFooter}><b>₹{Number(item.price || 0).toFixed(0)}</b><Link href={'/shop/' + item.shop_id} aria-label={'View ' + item.product_name}><ArrowUpRight size={17} /></Link></div>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className={styles.marketSection} aria-labelledby="products-heading">
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>{query.trim() ? 'MATCHING ITEMS' : 'HANDPICKED FOR YOU'}</span>
              <h2 id="products-heading">{query.trim() && mode === 'products' ? 'Products matching your search' : 'Popular products'}</h2>
              <p>Everyday essentials from your local stores.</p>
            </div>
            <Link href="/shops" className={styles.viewAllLink}>Explore <ChevronRight size={16} /></Link>
          </div>

          {productCategories.length > 1 && (
            <div className={styles.productCategoryRow}>
              {productCategories.map((category) => (
                <button key={category} type="button" className={activeProductCategory === category ? styles.productCategoryActive : styles.productCategory} onClick={() => setActiveProductCategory(category)}>
                  {category}
                </button>
              ))}
            </div>
          )}

          {filteredFeaturedProducts.length ? (
            <div className={styles.productGrid}>
              {filteredFeaturedProducts.slice(0, 8).map((product) => {
                const image = product.image_url ? resolveLogo(product.image_url) : '';
                const outOfStock = product.stock_available === 0;
                return (
                  <article className={styles.productCard} key={product.shop_id + ':' + product.product_id}>
                    <Link className={styles.productImageLink} href={'/shop/' + product.shop_id + '/product/' + product.product_id} aria-label={'View ' + product.product_name}>
                      <div className={styles.productPicture}>
                        {image ? <img src={image} alt={product.product_name} loading="lazy" /> : <ShoppingBasket size={38} />}
                      </div>
                      {outOfStock ? <span className={styles.stockBadge}>Out of stock</span> : <span className={styles.stockBadge + ' ' + styles.stockBadgeAvailable}>Local pick</span>}
                    </Link>
                    <div className={styles.productCardBody}>
                      <small>{product.shop_name}</small>
                      <Link href={'/shop/' + product.shop_id + '/product/' + product.product_id} className={styles.productTitle}>{product.product_name}</Link>
                      {product.category && <span className={styles.productCategoryLabel}>{product.category}</span>}
                      <div className={styles.productCardFooter}>
                        <b>₹{Number(product.price || 0).toFixed(0)}</b>
                        <button type="button" className={styles.addProductButton} onClick={() => addProduct(product)} disabled={outOfStock} aria-label={'Add ' + product.product_name + ' to cart'}>
                          <Plus size={18} />
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className={styles.emptyProducts}>
              <span><ShoppingBasket size={24} /></span>
              <strong>{loading ? 'Finding fresh products…' : query.trim() && mode !== 'shops' ? 'No matching products yet' : 'More local products are coming soon'}</strong>
              <p>{loading ? 'We are checking the local shelves.' : 'Browse a shop to discover the items available today.'}</p>
            </div>
          )}
        </section>

        <div className={styles.trustStrip}>
          <span><ShieldCheck size={16} /> Secure checkout</span>
          <span><Truck size={16} /> Local delivery</span>
          <span><Zap size={16} /> Stock-aware shopping</span>
        </div>
      </div>
    </div>
  );

}
