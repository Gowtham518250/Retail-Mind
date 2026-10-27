'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { ArrowRight, Boxes, ArrowUpRight, MapPin, Search, ShoppingBasket, ShieldCheck, Sparkles, Star, Store, Truck, Zap, Apple, Milk, Leaf, Plus, ShoppingCart, UserRound, ChevronRight, CheckCircle2 } from 'lucide-react';
import styles from './Home.module.css';
import { API_BASE } from '../lib/api';
import Tilt3D from './Tilt3D';
import MarketScene from './MarketScene';
import { Reveal, Stagger, StaggerItem, WordReveal } from './Reveal';
import ProductImage from './ProductImage';
import LocationModal from './LocationModal';
import { useCart } from '../context/CartContext';
import type { PublicProductPreview, PublicShop } from '../lib/publicCatalog';

// Deterministic colourways so every shop gets its own identity.
const SHOP_TONES = [
  ['#e9efff', '#cddcff', '#142857'],
  ['#e3faf4', '#bfeee1', '#17483e'],
  ['#f0edff', '#d9d3ff', '#2b255f'],
  ['#fff4df', '#ffe0ad', '#654b13'],
  ['#e7f6ff', '#c8eaff', '#163d5f'],
];

const resolveLogo = (url?: string) => (url ? (url.startsWith('http') ? url : API_BASE + url) : '');

function categoryIllustration(value?: string) {
  const text = String(value || '').toLowerCase();
  if (/beverage|drink|juice|tea|coffee|water/.test(text)) return '/categories/category-beverages.svg';
  if (/snack|bakery|biscuit|sweet|cake|chips/.test(text)) return '/categories/category-snacks.svg';
  if (/fruit|apple|banana|mango/.test(text)) return '/categories/category-fruits.svg';
  if (/vegetable|veggie|greens|leaf|produce/.test(text)) return '/categories/category-vegetables.svg';
  if (/dairy|milk|curd|yogurt|cheese|paneer/.test(text)) return '/categories/category-dairy.svg';
  if (/grocery|supermarket|provision|general store|rice|flour|sugar/.test(text)) return '/categories/category-groceries.svg';
  return '/categories/category-all.svg';
}

function ShopCard({ shop, index }: { shop: any; index: number }) {
  const [from, to, ink] = SHOP_TONES[Math.abs(Number(shop.shop_id) || index) % SHOP_TONES.length];
  const logo = resolveLogo(shop.logo_url);
  const shopIllustration = categoryIllustration(String(shop.shop_type || shop.shop_name || ''));
  const rated = Boolean(shop.rating_count);
  return (
    <StaggerItem className={styles.tiltFill}>
      <Tilt3D className={styles.tiltFill} max={9} lift={14}>
        <Link href={'/shop/' + shop.shop_id} className={styles.shopCard}>
          <div className={styles.shopVisual} style={{ background: `linear-gradient(135deg, ${from}, ${to})`, color: ink }}>
            <img src={shopIllustration} alt="" aria-hidden="true" className={styles.shopArt} loading="lazy" />
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
    </StaggerItem>
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
  const reduceMotion = Boolean(useReducedMotion());
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>('products');
  const [shops, setShops] = useState<any[]>(initialShops);
  const [products, setProducts] = useState<any[]>([]);
  const [featuredProducts, setFeaturedProducts] = useState<FeaturedProduct[]>(initialFeaturedProducts);
  const [activeProductCategory, setActiveProductCategory] = useState('All');
  const [aiMessage, setAiMessage] = useState('');
  const [aiResults, setAiResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(initialShops.length === 0);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [userArea, setUserArea] = useState('');
  const [locationModalOpen, setLocationModalOpen] = useState(false);
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const syncArea = () => {
      setUserArea(localStorage.getItem('retailMindArea') || '');
    };
    syncArea();
    window.addEventListener('storage', syncArea);
    window.addEventListener('retailmind:area', syncArea);
    return () => {
      window.removeEventListener('storage', syncArea);
      window.removeEventListener('retailmind:area', syncArea);
    };
  }, []);

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

  const areaLabel = useMemo(() => {
    const counts = new Map<string, number>();
    shops.forEach((shop) => {
      const city = typeof shop.city === 'string' ? shop.city.trim() : '';
      if (city) counts.set(city, (counts.get(city) || 0) + 1);
    });
    const top = Array.from(counts.entries()).sort((a, b) => b[1] - a[1])[0];
    return top ? top[0] : 'your neighbourhood';
  }, [shops]);

  useEffect(() => {
    if (areaLabel && areaLabel !== 'your neighbourhood') {
      try {
        if (!localStorage.getItem('retailMindArea')) {
          localStorage.setItem('retailMindArea', areaLabel);
          window.dispatchEvent(new Event('retailmind:area'));
        }
      } catch { /* storage unavailable */ }
    }
  }, [areaLabel]);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('q');
    if (q && q.trim()) { setMode('products'); setQuery(q); void performSearch('products', q, true); }
    // run once on arrival from the top-bar search
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        if (requestedMode === 'products') {
          setShops(initialShops);
          setProducts([]);
          setFeaturedProducts(initialFeaturedProducts);
          return;
        }
        const res = await fetch('/api/marketplace/search?mode=shops&limit=60', { cache: 'no-store', signal: controller.signal });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Marketplace API returned ' + res.status + '.');
        if (requestId !== requestIdRef.current) return;
        setShops(Array.isArray(data.shops) ? data.shops : []);
        setProducts([]);
        return;
      }

      const searchMode = requestedMode === 'shops' ? 'shops' : 'products';
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

  const selectMode = (nextMode: 'products' | 'shops') => {
    setMode(nextMode);
    setActiveProductCategory('All');
    setAiResults([]);
    setAiMessage('');
    setError('');

    if (nextMode === 'shops') {
      void performSearch('shops', query, true);
      return;
    }

    if (query.trim()) {
      void performSearch('products', query, true);
      return;
    }

    requestIdRef.current += 1;
    controllerRef.current?.abort();
    setLoading(false);
    setSearching(false);
    setShops(initialShops);
    setProducts([]);
    setFeaturedProducts(initialFeaturedProducts);
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
    void performSearch('shops', '');
    return () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  const preset = (value: string) => {
    setActiveProductCategory('All');
    setQuery(value);
    setMode('products');
    void performSearch('products', value, true);
  };


  const { addToCart, itemCount, toggleCart } = useCart();

  const searchModes: { id: 'products' | 'shops'; label: string; icon?: React.ReactNode }[] = [
    { id: 'shops', label: 'Shops', icon: <Store size={14} /> },
    { id: 'products', label: 'Products', icon: <Boxes size={14} /> },
  ];

  const categories = [
    { label: 'All', image: 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=240&q=80', tone: 'purple' },
    { label: 'Groceries', image: 'https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=240&q=80', tone: 'blue' },
    { label: 'Snacks', image: 'https://images.unsplash.com/photo-1566478989037-eec170784d0b?auto=format&fit=crop&w=240&q=80', tone: 'peach' },
    { label: 'Beverages', image: 'https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=240&q=80', tone: 'purple' },
    { label: 'Fruits', image: 'https://images.unsplash.com/photo-1619566636858-adf3ef46400b?auto=format&fit=crop&w=240&q=80', tone: 'pink' },
    { label: 'Vegetables', image: 'https://images.unsplash.com/photo-1597362925123-77861d3fbac7?auto=format&fit=crop&w=240&q=80', tone: 'green' },
    { label: 'Dairy', image: 'https://images.unsplash.com/photo-1550583724-b2692b85b150?auto=format&fit=crop&w=240&q=80', tone: 'yellow' },
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
        <button
          type="button"
          className={styles.locationGroupBtn}
          onClick={() => setLocationModalOpen(true)}
          title="Change location"
          aria-label={'Deliver to ' + (userArea || areaLabel) + ', click to change location'}
        >
          <span className={styles.locationIcon}><MapPin size={16} /></span>
          <span className={styles.locationCopy}>
            <small>SHOPPING NEAR</small>
            <strong>{userArea || areaLabel}</strong>
          </span>
          <ChevronRight size={15} className={styles.locationChevron} />
        </button>
        <div className={styles.headerActions}>
          <Link href="/shops" className={styles.desktopNavLink}><Store size={16} /> Shops</Link>
          <Link href="/ai-shopping" className={styles.desktopNavLink}><Sparkles size={16} /> AI shopping</Link>
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
        <section className={styles.freshBanner} aria-labelledby="fresh-banner-title">
          <div className={styles.freshBannerCopy}>
            <span className={styles.freshBadge}><CheckCircle2 size={14} /> LOCAL SHOPS · LIVE PRODUCTS · EASY CHECKOUT</span>
            <h1 id="fresh-banner-title">
              <WordReveal text={mode === 'shops' ? 'Find your next' : 'Think it. Say it.'} delay={0.1} />{' '}
              <WordReveal text={mode === 'shops' ? 'favourite shop.' : 'Shop it.'} className={styles.heroAccent} delay={0.5} />
            </h1>
            <p>{mode === 'shops'
              ? 'Explore nearby shops, compare ratings and discover products available around you.'
              : 'Tell us what you need. Browse trusted neighbourhood stores and find everyday essentials in one place.'}</p>
            <form
              className={styles.marketSearch}
              role="search"
              onSubmit={(event) => { event.preventDefault(); void performSearch(mode, query, true); }}
            >
              <Search size={20} className={styles.marketSearchIcon} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={mode === 'shops' ? 'Search shops or locations' : 'Try “best rated shampoo under ₹500”'}
                aria-label={mode === 'shops' ? 'Search for shops or locations' : 'Search for products or categories'}
              />
              <motion.button
                type="submit"
                disabled={searching}
                whileHover={reduceMotion || searching ? undefined : { scale: 1.03 }}
                whileTap={reduceMotion ? undefined : { scale: 0.97 }}
              >{searching ? 'Finding…' : 'Find matches'}</motion.button>
            </form>
            <div className={styles.discoveryControls} aria-label="Choose what to browse">
              <div className={styles.discoveryTabs} role="tablist" aria-label="Marketplace results">
                {searchModes.slice().reverse().map((searchMode) => (
                  <button
                    type="button"
                    key={searchMode.id}
                    role="tab"
                    aria-selected={mode === searchMode.id}
                    className={mode === searchMode.id ? styles.discoveryTabActive : styles.discoveryTab}
                    onClick={() => selectMode(searchMode.id)}
                  >
                    {searchMode.icon}
                    {searchMode.label}
                  </button>
                ))}
              </div>
              <Link href="/ai-shopping" className={styles.aiShortcut}>
                <Sparkles size={15} />
                Ask AI to find it
                <ArrowRight size={14} />
              </Link>
            </div>
            <div className={styles.quickChips} aria-label="Popular searches">
              {['low price rice', 'best rated atta', 'milk under ₹80', 'low price ghee'].map((suggestion) => (
                <button type="button" key={suggestion} onClick={() => preset(suggestion)}>{suggestion}</button>
              ))}
            </div>
            <div className={styles.dashboardCtaRow}>
              <Link
                href="https://github.com/Gowtham518250/Retail-Mind/tree/frontend-web-launch"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.dashboardCta}
              >
                <Store size={17} />
                Shop owner dashboard
                <ArrowUpRight size={16} />
              </Link>
              <span className={styles.dashboardHint}>For shop owners</span>
            </div>
          </div>
          <div className={styles.freshArtwork} aria-hidden="true">
            <span className={styles.artHalo} />
            <motion.span
              className={styles.artTile + ' ' + styles.artTileOne}
              whileHover={reduceMotion ? undefined : { scale: 1.12, rotate: 8 }}
            ><Apple size={32} /></motion.span>
            <motion.span
              className={styles.artTile + ' ' + styles.artTileTwo}
              whileHover={reduceMotion ? undefined : { scale: 1.12, rotate: -6 }}
            ><Milk size={30} /></motion.span>
            <motion.span
              className={styles.artTile + ' ' + styles.artTileThree}
              whileHover={reduceMotion ? undefined : { scale: 1.12, rotate: 10 }}
            ><Leaf size={30} /></motion.span>
            <motion.div
              className={styles.artBasket}
              whileHover={reduceMotion ? undefined : { scale: 1.05, rotate: 2 }}
              transition={{ type: 'spring', stiffness: 260, damping: 18 }}
            >
              <MarketScene compact />
            </motion.div>
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

        {mode === 'products' && <Reveal as="section" className={styles.marketSection} id="categories" aria-label="Shop by category">
          <Stagger className={styles.categoryGrid} stagger={0.05}>
            {categories.map((category) => (
              <StaggerItem key={category.label}>
              <button
                type="button"
                className={styles.categoryButton}
                onClick={() => {
                  setActiveProductCategory('All');
                  if (category.label === 'All') {
                    setQuery('');
                    setMode('products');
                    void performSearch('products', '', true);
                  } else {
                    preset(category.label);
                  }
                }}
              >
                <span className={styles.categoryIcon + ' ' + styles['category' + category.tone]}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={category.image} alt={category.label} loading="lazy" />
                </span>
                <span>{category.label}</span>
              </button>
              </StaggerItem>
            ))}
          </Stagger>
        </Reveal>}

        {mode === 'shops' && <Reveal as="section" className={styles.marketSection} id="shops" aria-labelledby="shops-heading">
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>{query.trim() ? 'Your search' : 'Close to home'}</span>
              <h2 id="shops-heading">{query.trim() ? (mode === 'shops' ? 'Shops matching your search' : 'Search results') : 'Nearby shops'}</h2>
              <p>{query.trim() ? 'Explore matching local stores and the products they offer.' : 'Stores that are open and ready for your next order.'}</p>
            </div>
            <Link href="/shops" className={styles.viewAllLink}>View all <ChevronRight size={16} /></Link>
          </div>

          {loading ? (
            <div className={styles.shopsGrid}>
              {Array.from({ length: 3 }).map((_, index) => <div className={styles.marketSkeleton} key={index} />)}
            </div>
          ) : shops.length ? (
            <Stagger className={styles.shopsGrid} key={shops.length + ':' + query.trim()}>
              {shops.slice(0, query.trim() ? 12 : 6).map((shop, index) => <ShopCard key={shop.shop_id} shop={shop} index={index} />)}
            </Stagger>
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
        </Reveal>}

        {mode === 'products' && aiResults.length > 0 && (
          <section className={styles.marketSection} aria-labelledby="ai-results-heading">
            <div className={styles.sectionHeader}>
              <div><span className={styles.sectionEyebrow}>Picked for you</span><h2 id="ai-results-heading">Recommended for you</h2></div>
            </div>
            <div className={styles.productGrid}>
              {aiResults.map((item, index) => (
                <article className={styles.productCard} key={String(item.product_id) + '-' + String(item.shop_id) + '-' + String(index)}>
                  <div className={styles.productPicture}>
                    <ProductImage src={item.image_url} name={item.product_name} category={item.category} />
                  </div>
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

        {mode === 'products' && <Reveal as="section" className={styles.marketSection} aria-labelledby="products-heading">
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>{query.trim() ? 'Matching items' : 'Fresh on the shelves'}</span>
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
            <Stagger className={styles.productGrid} stagger={0.06} key={activeProductCategory + ':' + filteredFeaturedProducts.length}>
              {filteredFeaturedProducts.slice(0, 8).map((product) => {
                const outOfStock = product.stock_available === 0;
                return (
                  <StaggerItem key={product.shop_id + ':' + product.product_id} className={styles.cell}>
                  <article className={styles.productCard}>
                    <Link className={styles.productImageLink} href={'/shop/' + product.shop_id + '/product/' + product.product_id} aria-label={'View ' + product.product_name}>
                      <div className={styles.productPicture}>
                        <ProductImage
                          src={product.image_url}
                          name={product.product_name}
                          category={product.category}
                        />
                      </div>
                      {outOfStock ? <span className={styles.stockBadge}>Out of stock</span> : <span className={styles.stockBadge + ' ' + styles.stockBadgeAvailable}>Local pick</span>}
                    </Link>
                    <div className={styles.productCardBody}>
                      <small>{product.shop_name}</small>
                      <Link href={'/shop/' + product.shop_id + '/product/' + product.product_id} className={styles.productTitle}>{product.product_name}</Link>
                      {product.category && <span className={styles.productCategoryLabel}>{product.category}</span>}
                      <div className={styles.productCardFooter}>
                        <b>₹{Number(product.price || 0).toFixed(0)}</b>
                        <motion.button
                          type="button"
                          className={styles.addProductButton}
                          onClick={() => addProduct(product)}
                          disabled={outOfStock}
                          aria-label={'Add ' + product.product_name + ' to cart'}
                          whileHover={reduceMotion || outOfStock ? undefined : { scale: 1.1, rotate: 90 }}
                          whileTap={reduceMotion ? undefined : { scale: 0.9 }}
                        >
                          <Plus size={18} />
                        </motion.button>
                      </div>
                    </div>
                  </article>
                  </StaggerItem>
                );
              })}
            </Stagger>
          ) : (
            <div className={styles.emptyProducts}>
              <span><ShoppingBasket size={24} /></span>
              <strong>{loading ? 'Finding fresh products…' : query.trim() && mode === 'products' ? 'No matching products yet' : 'More local products are coming soon'}</strong>
              <p>{loading ? 'We are checking the local shelves.' : 'Browse a shop to discover the items available today.'}</p>
            </div>
          )}
        </Reveal>}

        <Stagger className={styles.trustStrip} stagger={0.08}>
          <StaggerItem><span><ShieldCheck size={16} /> Secure checkout</span></StaggerItem>
          <StaggerItem><span><Truck size={16} /> Local delivery</span></StaggerItem>
          <StaggerItem><span><Zap size={16} /> Stock-aware shopping</span></StaggerItem>
        </Stagger>
      </div>

      <LocationModal
        isOpen={locationModalOpen}
        onClose={() => setLocationModalOpen(false)}
        onLocationSelected={(newArea: string) => setUserArea(newArea)}
      />
    </div>
  );

}
