'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { AnimatePresence, motion } from 'framer-motion';
import { Search, SlidersHorizontal, Sparkles, Phone, MapPin, PackageCheck, ShieldCheck, ArrowRight, Globe, Star, Store, X } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { API_BASE } from '../lib/api';
import type { ShopProduct, ShopResponse } from '../lib/types';
import ProductCard from './ProductCard';
import styles from './Storefront.module.css';

const HeroScene3D = dynamic(() => import('./HeroScene3D'), { ssr: false });
const EASE = [0.2, 0.75, 0.25, 1] as const;

interface StorefrontShellProps {
  shopId: number;
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

function Words({ text, base = 0 }: { text: string; base?: number }) {
  return (
    <>
      {text.split(' ').map((word, i) => (
        <span key={i + word}><span className={styles.wordMask}>
          <motion.span
            className={styles.word}
            initial={{ y: '115%', rotate: 4 }}
            animate={{ y: 0, rotate: 0 }}
            transition={{ duration: 0.8, delay: base + i * 0.08, ease: EASE }}
          >
            {word}
          </motion.span>
        </span>{' '}</span>
      ))}
    </>
  );
}

export default function StorefrontShell({ shopId }: StorefrontShellProps) {
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [shop, setShop] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'featured' | 'price-low' | 'price-high' | 'discount'>('featured');
  const [activeCategory, setActiveCategory] = useState('All');
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const { addToCart, cartItems } = useCart();

  useEffect(() => {
    const loadShop = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`${API_BASE}/store/shops/${shopId}/products`);
        if (!res.ok) throw new Error('Unable to load this shop right now.');
        const data = await res.json();
        setShop(data);
        setProducts(data.products || []);
      } catch (err: any) {
        setError(err.message || 'Something went wrong.');
      } finally {
        setLoading(false);
      }
    };

    loadShop();
  }, [shopId]);

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
    addToCart({ ...product, shop_id: shopId });
    setJustAddedId(product.id);
    window.setTimeout(() => setJustAddedId(null), 1200);
  };

  const logo = shop?.shop_logo_url ? (shop.shop_logo_url.startsWith('http') ? shop.shop_logo_url : API_BASE + shop.shop_logo_url) : '';
  const rating = Number(shop?.rating || 0);

  return (
    <div className={styles.page}>
      {/* ───────── shop hero ───────── */}
      <section className={styles.hero}>
        <div className={styles.heroBg} aria-hidden="true" />
        <div className={styles.grain} aria-hidden="true" />

        <div className={styles.heroCopy}>
          <motion.div className={styles.identity} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease: EASE }}>
            <div className={styles.avatar}>
              {logo ? <img src={logo} alt={(shop?.shop_name || 'Shop') + ' profile'} /> : <Store size={32} strokeWidth={1.6} />}
            </div>
            <div>
              <div className={styles.type}><span className={styles.pulse} /> {shop?.shop_type || 'Local storefront'} · Online</div>
              <div className={styles.ratingRow}>
                <StarRating value={rating} />
                <b>{rating > 0 ? rating.toFixed(1) : 'New'}</b>
                <span>{Number(shop?.rating_count || 0)} verified reviews</span>
              </div>
            </div>
          </motion.div>

          <h1 className={styles.title}><Words text={shop?.shop_name || 'Retail Mind Storefront'} base={0.1} /></h1>

          <motion.p className={styles.tagline} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, delay: 0.5, ease: EASE }}>
            {shop?.shop_tagline || shop?.shop_description || 'Discover fresh essentials, daily deals, and a delightful shopping experience built for modern customers.'}
          </motion.p>

          <motion.div className={styles.metaRow} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.65 }}>
            {shop?.shop_phone && <span><Phone size={15} /> {shop.shop_phone}</span>}
            {(shop?.shop_city || shop?.shop_address) && <span><MapPin size={15} /> {shop.shop_city || shop.shop_address}</span>}
            {shop?.shop_website && <span><Globe size={15} /> {shop.shop_website}</span>}
          </motion.div>

          <motion.div className={styles.stats} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.75, duration: 0.6, ease: EASE }}>
            <span><PackageCheck size={17} /> {products.length} products</span>
            <span><ShieldCheck size={17} /> Customer-only order access</span>
            <span><Sparkles size={17} /> Shop-provided product details</span>
            {(shop?.online_setup_fee || 0) > 0 && <span><b className={styles.rupee}>₹</b> Online setup fee ₹{Number(shop?.online_setup_fee || 0).toFixed(2)}</span>}
          </motion.div>

          <motion.div className={styles.ctas} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.9, duration: 0.6, ease: EASE }}>
            <Link href="#products" className={styles.ctaMain}>Shop now <ArrowRight size={18} /></Link>
            <Link href="/orders" className={styles.ctaGhost}>My orders</Link>
          </motion.div>
          <p className={styles.note}>Browse freely · Sign in only when you checkout</p>
        </div>

        <div className={styles.stage}>
          <div className={styles.stageGlow} aria-hidden="true" />
          <HeroScene3D lite className={styles.canvas} />
          <motion.div className={styles.floatChip} animate={{ y: [0, -9, 0] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}>
            <span className={styles.floatIcon}><PackageCheck size={16} /></span>
            <span><b>{loading ? 'Loading shelves…' : `${products.length} products`}</b><small>Availability shown per item</small></span>
          </motion.div>
        </div>
      </section>

      {/* ───────── sticky controls ───────── */}
      <div className={styles.toolbarWrap}>
        <section className={styles.toolbar} aria-label="Store controls">
          <label className={styles.searchBox}>
            <Search size={18} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search by product, category or keyword" />
            <AnimatePresence>
              {search && (
                <motion.button initial={{ scale: 0 }} animate={{ scale: 1 }} exit={{ scale: 0 }} className={styles.clear} onClick={() => setSearch('')} aria-label="Clear search" type="button">
                  <X size={14} />
                </motion.button>
              )}
            </AnimatePresence>
          </label>

          <div className={styles.sort}>
            <SlidersHorizontal size={16} />
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value as any)} aria-label="Sort products">
              <option value="featured">Featured</option>
              <option value="price-low">Price: Low to High</option>
              <option value="price-high">Price: High to Low</option>
              <option value="discount">Best discount</option>
            </select>
          </div>

          <div className={styles.cats} role="tablist" aria-label="Categories">
            {categories.map((category) => (
              <button key={category} role="tab" aria-selected={activeCategory === category} className={`${styles.cat} ${activeCategory === category ? styles.catOn : ''}`} onClick={() => setActiveCategory(category)}>
                {activeCategory === category && <motion.span layoutId="catPill" className={styles.catPill} transition={{ type: 'spring', stiffness: 420, damping: 34 }} />}
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
            <p className={styles.kicker}>Curated for you</p>
            <h2>Popular picks</h2>
          </div>
          <div className={styles.count}>{filteredProducts.length} items</div>
        </div>

        {loading ? (
          <div className={styles.grid}>{Array.from({ length: 8 }).map((_, index) => <div key={index} className={styles.skeleton} />)}</div>
        ) : error ? (
          <div className={styles.empty}><strong>Couldn&apos;t open this shop</strong><p>{error}</p></div>
        ) : filteredProducts.length === 0 ? (
          <div className={styles.empty}><strong>Nothing matches yet</strong><p>No products match your search. Try another keyword.</p></div>
        ) : (
          <motion.div className={styles.grid} layout>
            <AnimatePresence mode="popLayout" initial={false}>
              {filteredProducts.map((product, index) => (
                <motion.div
                  key={product.id}
                  layout
                  initial={{ opacity: 0, y: 36, scale: 0.94 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.5, delay: Math.min(index, 10) * 0.04, ease: EASE }}
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
    </div>
  );
}
