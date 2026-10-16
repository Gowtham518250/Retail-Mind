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
  const productCover = products.find((product) => typeof product.image_url === 'string' && product.image_url.trim())?.image_url || '';
  const bannerImage = productCover ? (productCover.startsWith('http') ? productCover : API_BASE + (productCover.startsWith('/') ? productCover : '/' + productCover)) : '';

  return (
    <div className={styles.page}>
      {/* Shop banner: compact like the supplied storefront screen */}
      <section
        className={styles.storeBanner}
        style={bannerImage ? { backgroundImage: 'linear-gradient(90deg, rgba(7,20,45,.94) 0%, rgba(7,20,45,.76) 48%, rgba(7,20,45,.38) 100%), url("' + bannerImage + '")' } : undefined}
      >
        <Link href="/" className={styles.storeBannerBack}><ArrowLeft size={15} /> Marketplace</Link>
        <div className={styles.storeBannerContent}>
          <div className={styles.storeBannerAvatar}>
            {logo ? <img src={logo} alt="" /> : <Store size={25} />}
          </div>
          <div className={styles.storeBannerInfo}>
            <div className={styles.storeBannerMeta}>
              <span className={styles.storeBannerLive}><i /> Shop storefront</span>
              <span className={styles.storeBannerRating}><Star size={12} fill="currentColor" /> {rating > 0 ? rating.toFixed(1) : 'New'} · {Number(shop?.rating_count || 0)} reviews</span>
            </div>
            <h1>{shop?.shop_name || 'Local Store'}</h1>
            <p>{shop?.shop_tagline || shop?.shop_description || 'Browse the products listed by this neighbourhood shop.'}</p>
            <div className={styles.storeBannerDetails}>
              {(shop?.shop_city || shop?.shop_address) && <span><MapPin size={13} /> {shop.shop_city || shop.shop_address}</span>}
              <span><PackageCheck size={13} /> {products.length} products listed</span>
              {shop?.shop_phone && <span><Phone size={13} /> {shop.shop_phone}</span>}
            </div>
          </div>
          <div className={styles.storeBannerActions}>
            <Link href="#products" className={styles.storeBannerShopNow}>Shop now <ArrowRight size={15} /></Link>
            <Link href="/orders" className={styles.storeBannerOrders}>Orders</Link>
          </div>
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
