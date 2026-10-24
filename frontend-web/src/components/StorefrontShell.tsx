'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Search, SlidersHorizontal, Phone, MapPin, Truck, ShoppingBag, Wallet, Share2, Navigation, Star, Store, X, Clock } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { API_BASE } from '../lib/api';
import { trackEvent } from '../lib/analytics';
import type { ShopProduct, ShopResponse } from '../lib/types';
import ProductCard from './ProductCard';
import styles from './Storefront.module.css';

const EASE = [0.2, 0.75, 0.25, 1] as const;

interface StorefrontShellProps {
  shopId: number;
  initialData?: ShopResponse | null;
}

function StarRating({ value }: { value: number }) {
  return (
    <span className={styles.stars} aria-label={(value || 0) + ' out of 5'}>
      {Array.from({ length: 5 }, (_, index) => (
        <Star key={index} size={14} fill={index < Math.round(value) ? 'currentColor' : 'none'} />
      ))}
    </span>
  );
}

function Words({ text }: { text: string }) {
  return <>{text}</>;
}

export default function StorefrontShell({ shopId, initialData = null }: StorefrontShellProps) {
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [products, setProducts] = useState<ShopProduct[]>(initialData?.products || []);
  const [shop, setShop] = useState<ShopResponse | null>(initialData);
  const [loading, setLoading] = useState(!initialData?.products?.length);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'featured' | 'price-low' | 'price-high' | 'discount'>('featured');
  const [activeCategory, setActiveCategory] = useState('All');
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const [reloadCount, setReloadCount] = useState(0);
  const { addToCart, cartItems } = useCart();
  const [tab, setTab] = useState<'products' | 'about' | 'reviews'>('products');
  const [reviews, setReviews] = useState<{ id: number; rating?: number; comment?: string; customer_name?: string; created_at?: string }[]>([]);
  const [reviewsLoaded, setReviewsLoaded] = useState(false);
  const [shareNote, setShareNote] = useState('');

  useEffect(() => {
    if (tab !== 'reviews' || reviewsLoaded) return;
    const controller = new AbortController();
    fetch(API_BASE + '/store/shops/' + shopId + '/reviews?limit=20', { cache: 'no-store', signal: controller.signal })
      .then((res) => (res.ok ? res.json() : { reviews: [] }))
      .then((data) => setReviews(Array.isArray(data.reviews) ? data.reviews : []))
      .catch(() => setReviews([]))
      .finally(() => setReviewsLoaded(true));
    return () => controller.abort();
  }, [tab, reviewsLoaded, shopId]);

  const shareShop = async () => {
    const url = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: shop?.shop_name || 'Retail Mind shop', url });
      else { await navigator.clipboard.writeText(url); setShareNote('Link copied'); window.setTimeout(() => setShareNote(''), 1800); }
    } catch { /* share cancelled */ }
  };

  useEffect(() => {
    if (initialData?.products?.length && reloadCount === 0) {
      setShop(initialData);
      setProducts(initialData.products);
      setLoading(false);
      setError('');
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    const loadShop = async () => {
      setLoading(!initialData?.products?.length);
      setError('');
      try {
        const res = await fetch(`/api/marketplace/shops/${shopId}/products`, {
          signal: controller.signal,
          cache: 'no-store',
          headers: { Accept: 'application/json' },
        });
        const data = await res.json() as Partial<ShopResponse> & { detail?: string };
        if (!res.ok) {
          throw new Error(data.detail || 'Unable to load this shop right now.');
        }
        if (typeof data.shop_name !== 'string' || !Array.isArray(data.products)) {
          throw new Error('The shop returned an unexpected response. Please try again.');
        }
        if (cancelled) return;
        setShop(data as ShopResponse);
        setProducts(data.products);
      } catch (err: any) {
        if (cancelled) return;
        setError(err instanceof TypeError
          ? 'We couldn’t reach this shop. Check your connection and try again.'
          : err.message || 'Something went wrong.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadShop();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [initialData, shopId, reloadCount]);

  useEffect(() => {
    if (!shop?.shop_name) return;
    trackEvent('shop_view', {
      shop_id: shopId,
      shop_name: shop.shop_name,
      shop_type: shop.shop_type || 'Local shop',
      product_count: products.length,
    });
  }, [products.length, shop?.shop_name, shop?.shop_type, shopId]);

  const categories = useMemo(() => {
    const unique = Array.from(new Set(products.map((product) => product.category).filter(Boolean))) as string[];
    return ['All', ...unique];
  }, [products]);

  const filteredProducts = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    let list = [...products];

    if (normalized) {
      list = list.filter((product) => {
        const haystack = `${product.name} ${product.category || ''} ${product.description || ''}`.toLowerCase();
        return haystack.includes(normalized);
      });
    }

    if (activeCategory !== 'All') {
      list = list.filter((product) => product.category === activeCategory);
    }

    switch (sortBy) {
      case 'price-low':
        list.sort((a, b) => a.price - b.price);
        break;
      case 'price-high':
        list.sort((a, b) => b.price - a.price);
        break;
      case 'discount':
        list.sort((a, b) => (b.discount_pct || 0) - (a.discount_pct || 0));
        break;
      default:
        list.sort((a, b) => Number(b.flash_sale_active) - Number(a.flash_sale_active));
        break;
    }

    return list;
  }, [activeCategory, products, search, sortBy]);

  const handleAddToCart = (product: ShopProduct) => {
    if (!addToCart({ ...product, shop_id: shopId })) return false;
    setJustAddedId(product.id);
    window.setTimeout(() => setJustAddedId(null), 1200);
    return true;
  };

  const logo = shop?.shop_logo_url ? (shop.shop_logo_url.startsWith('http') ? shop.shop_logo_url : API_BASE + shop.shop_logo_url) : '';
  const rating = Number(shop?.rating || 0);

  return (
    <div className={styles.page} data-experience="storefront">
      {/* ───────── shop header ───────── */}
      <section className={styles.hero}>
        <div className={styles.cover} aria-hidden="true" />
        <div className={styles.heroInner}>
          <div className={styles.avatar}>
            {logo ? <Image src={logo} alt={(shop?.shop_name || 'Shop') + ' logo'} width={88} height={88} sizes="88px" fetchPriority="high" decoding="async" /> : <Store size={34} strokeWidth={1.7} />}
          </div>
          <div className={styles.heroText}>
            <h1 className={styles.title}>{shop?.shop_name || 'Retail Mind storefront'}</h1>
            <p className={styles.tagline}>{shop?.shop_tagline || shop?.shop_description || shop?.shop_type || 'Local shop'}</p>
            <div className={styles.ratingRow}>
              <StarRating value={rating} />
              <b>{rating > 0 ? rating.toFixed(1) : 'New'}</b>
              <span>({Number(shop?.rating_count || 0)} reviews)</span>
              <span className={styles.open}><i /> Open</span>
              {(shop?.shop_city || shop?.shop_address) && <span className={styles.where}><MapPin size={14} /> {shop.shop_city || shop.shop_address}</span>}
            </div>
          </div>
          <div className={styles.actions}>
            <button type="button" className={styles.actionBtn} onClick={shareShop}><Share2 size={17} /> {shareNote || 'Share'}</button>
            {shop?.shop_phone && <a className={styles.actionBtn} href={'tel:' + shop.shop_phone.replace(/\s+/g, '')}><Phone size={17} /> Call</a>}
            {(shop?.shop_address || shop?.shop_city) && (
              <a className={`${styles.actionBtn} ${styles.actionPrimary}`} target="_blank" rel="noreferrer"
                href={'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent([shop?.shop_name, shop?.shop_address, shop?.shop_city].filter(Boolean).join(', '))}>
                <Navigation size={17} /> Directions
              </a>
            )}
          </div>
        </div>
        <ul className={styles.facts}>
          {shop?.offer_delivery !== false && <li><Truck size={16} /> {Number(shop?.delivery_fee || 0) > 0 ? 'Delivery ₹' + Number(shop?.delivery_fee) : 'Free delivery'}</li>}
          {shop?.offer_pickup && <li><ShoppingBag size={16} /> Pickup available</li>}
          {Number(shop?.min_order || 0) > 0 && <li><Wallet size={16} /> Min order ₹{Number(shop?.min_order)}</li>}
          <li><Clock size={16} /> {products.length} products</li>
        </ul>
      </section>

      <div className={styles.tabs} role="tablist" aria-label="Shop sections">
        {(['products', 'about', 'reviews'] as const).map((key) => (
          <button key={key} role="tab" type="button" aria-selected={tab === key} className={`${styles.tab} ${tab === key ? styles.tabOn : ''}`} onClick={() => setTab(key)}>
            {key === 'products' ? 'Products' : key === 'about' ? 'About' : 'Reviews'}
          </button>
        ))}
      </div>

      {tab === 'about' && (
        <section className={styles.panel} role="tabpanel">
          <h2>About {shop?.shop_name}</h2>
          <p>{shop?.shop_description || shop?.shop_tagline || 'This shop has not added a description yet.'}</p>
          <dl className={styles.aboutGrid}>
            {shop?.shop_address && <div><dt>Address</dt><dd>{[shop.shop_address, shop.shop_city, shop.shop_state, shop.shop_postal_code].filter(Boolean).join(', ')}</dd></div>}
            {shop?.shop_phone && <div><dt>Phone</dt><dd>{shop.shop_phone}</dd></div>}
            {shop?.shop_categories && <div><dt>Sells</dt><dd>{shop.shop_categories.split(',').map((c) => c.trim()).filter(Boolean).join(' · ')}</dd></div>}
            <div><dt>Fulfilment</dt><dd>{[shop?.offer_delivery !== false && 'Home delivery', shop?.offer_pickup && 'Store pickup'].filter(Boolean).join(' · ') || 'Contact the shop'}</dd></div>
            <div><dt>Payments</dt><dd>{[shop?.accept_cod && 'Cash on delivery', shop?.accept_online && 'UPI / cards'].filter(Boolean).join(' · ') || 'Choose at checkout'}</dd></div>
          </dl>
        </section>
      )}

      {tab === 'reviews' && (
        <section className={styles.panel} role="tabpanel">
          <h2>Customer reviews</h2>
          {!reviewsLoaded ? <p>Loading reviews…</p> : reviews.length === 0 ? <p>No reviews yet. Be the first after your order is delivered.</p> : (
            <div className={styles.reviewList}>
              {reviews.map((review) => (
                <article key={review.id} className={styles.review}>
                  <header><strong>{review.customer_name || 'Customer'}</strong><StarRating value={Number(review.rating || 0)} /></header>
                  {review.comment && <p>{review.comment}</p>}
                  {review.created_at && <small>{new Date(review.created_at).toLocaleDateString('en-IN')}</small>}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ───────── sticky controls ───────── */}
      {tab === 'products' && (<>
      <div className={styles.toolbarWrap}>
        <section className={styles.toolbar} aria-label="Store controls">
          <label className={styles.searchBox}>
            <Search size={18} />
            <input
              type="search"
              inputMode="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by product, category or keyword"
              aria-label="Search this shop's products"
            />
            <AnimatePresence>
              {search && (
                <motion.button initial={shouldReduceMotion ? false : { scale: 0 }} animate={{ scale: 1 }} exit={shouldReduceMotion ? undefined : { scale: 0 }} transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.16 }} className={styles.clear} onClick={() => setSearch('')} aria-label="Clear search" type="button">
                  <X size={14} />
                </motion.button>
              )}
            </AnimatePresence>
          </label>

          <div className={styles.sort}>
            <SlidersHorizontal size={16} />
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as typeof sortBy)} aria-label="Sort products">
              <option value="featured">Featured</option>
              <option value="price-low">Price: Low to High</option>
              <option value="price-high">Price: High to Low</option>
              <option value="discount">Best discount</option>
            </select>
          </div>

          <div className={styles.cats} role="group" aria-label="Filter products by category">
            {categories.map((category) => (
              <button key={category} type="button" aria-pressed={activeCategory === category} className={`${styles.cat} ${activeCategory === category ? styles.catOn : ''}`} onClick={() => setActiveCategory(category)}>
                {activeCategory === category && (shouldReduceMotion ? <span className={styles.catPill} /> : <motion.span layoutId="catPill" className={styles.catPill} transition={{ type: 'spring', stiffness: 420, damping: 34 }} />)}
                <span className={styles.catLabel}>{category}</span>
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* ───────── products ───────── */}
      <section id="products" className={styles.products}>
        <div className={styles.head}>
          <div>
            <p className={styles.kicker}>Fresh on the shelves</p>
            <h2>Products</h2>
          </div>
          <div className={styles.count} aria-live="polite">
            {filteredProducts.length} {filteredProducts.length === 1 ? 'item' : 'items'}
          </div>
        </div>

        {loading ? (
          <div className={styles.grid}>{Array.from({ length: 8 }).map((_, index) => <div key={index} className={styles.skeleton} />)}</div>
        ) : error ? (
          <div className={styles.empty} role="alert">
            <strong>Couldn&apos;t open this shop</strong>
            <p>{error}</p>
            <button
              type="button"
              className={styles.retry}
              onClick={() => setReloadCount((count) => count + 1)}
            >
              Try again
            </button>
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className={styles.empty}>
            <strong>{products.length ? 'Nothing matches yet' : 'No products listed yet'}</strong>
            <p>
              {products.length
                ? 'No products match your current search and filters.'
                : 'This shop has not listed any products yet.'}
            </p>
            {products.length > 0 && (
              <button
                type="button"
                className={styles.retry}
                onClick={() => {
                  setSearch('');
                  setActiveCategory('All');
                  setSortBy('featured');
                }}
              >
                Clear search and filters
              </button>
            )}
          </div>
        ) : (
          <motion.div className={styles.grid} layout>
            <AnimatePresence mode="popLayout" initial={false}>
              {filteredProducts.map((product, index) => (
                <motion.div
                  key={product.id}
                  layout
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={shouldReduceMotion ? undefined : { opacity: 0 }}
                  transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.28, delay: Math.min(index, 5) * 0.025, ease: EASE }}
                  className={styles.cell}
                >
                  <ProductCard
                    product={product}
                    shopId={shopId}
                    inCartCount={cartItems.find((item) => item.product.id === product.id)?.quantity || 0}
                    justAdded={justAddedId === product.id}
                    onAddToCart={handleAddToCart}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </section>
      </>)}
    </div>
  );
}
