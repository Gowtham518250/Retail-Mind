'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Sparkles, Store, ShoppingBag, Star, ArrowRight } from 'lucide-react';
import { API_BASE } from '../lib/api';
import styles from './MarketplaceShell.module.css';

type ResultMode = 'all' | 'shops' | 'products' | 'ai';

export default function MarketplaceShell() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>('all');
  const [shops, setShops] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [ai, setAi] = useState<any[]>([]);
  const [aiMessage, setAiMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);

  const loadShops = async () => {
    setLoading(true);
    try {
      const res = await fetch(API_BASE + '/store/shops/nearby?limit=60', { cache: 'no-store' });
      const data = await res.json();
      setShops(data.shops || []);
      setProducts([]);
      setAi([]);
      setAiMessage('');
    } finally {
      setLoading(false);
    }
  };

  const runSearch = async () => {
    const value = query.trim();
    if (!value) {
      await loadShops();
      return;
    }

    setSearching(true);
    try {
      if (mode === 'ai') {
        const res = await fetch(
          API_BASE + '/store/ai/recommend?q=' + encodeURIComponent(value) + '&limit=10',
          { cache: 'no-store' },
        );
        const data = await res.json();
        setAi(data.recommendations || []);
        setAiMessage(data.response || '');
        setShops([]);
        setProducts([]);
      } else {
        const searchMode = mode === 'shops' ? 'shops' : mode === 'products' ? 'products' : 'all';
        const res = await fetch(
          API_BASE + '/store/marketplace/search?q=' + encodeURIComponent(value) +
            '&mode=' + searchMode + '&limit=30',
          { cache: 'no-store' },
        );
        const data = await res.json();
        setShops(data.shops || []);
        setProducts(data.products || []);
        setAi([]);
        setAiMessage('');
      }
    } finally {
      setSearching(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadShops();
  }, []);

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroGlow} />
        <div className={styles.heroTop}>
          <span className={styles.eyebrow}>RETAIL MIND MARKETPLACE</span>
          <span className={styles.livePill}>Online shops only</span>
        </div>
        <h1>Find the right shop. Compare products. Order in one place.</h1>
        <p>
          Search by shop name, search a product across multiple shops, or ask the shopping
          assistant for low-price and rating-aware recommendations.
        </p>

        <div className={styles.searchShell}>
          <Search size={21} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void runSearch();
            }}
            placeholder="Search shop name or product name"
          />
          <button onClick={() => void runSearch()} disabled={searching}>
            {searching ? 'Searching…' : 'Search'}
          </button>
        </div>

        <div className={styles.modeRow}>
          {[
            ['all', 'All'],
            ['shops', 'Shops'],
            ['products', 'Products'],
            ['ai', 'AI advice'],
          ].map(([value, label]) => (
            <button
              key={value}
              className={mode === value ? styles.modeActive : styles.mode}
              onClick={() => {
                setMode(value as ResultMode);
                if (query.trim()) void runSearch();
              }}
            >
              {value === 'ai' ? <Sparkles size={15} /> : null}
              {label}
            </button>
          ))}
        </div>
      </section>

      {aiMessage ? (
        <section className={styles.aiBanner}>
          <Sparkles size={19} />
          <div>
            <strong>Shopping assistant</strong>
            <p>{aiMessage}</p>
          </div>
        </section>
      ) : null}

      {loading ? (
        <div className={styles.center}>Loading marketplace…</div>
      ) : query.trim() && mode === 'ai' ? (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>AI CURATED</span>
              <h2>Top recommendations</h2>
            </div>
            <span className={styles.count}>{ai.length} matches</span>
          </div>
          <div className={styles.list}>
            {ai.map((item, index) => (
              <Link key={item.product_id} href={'/?shop_id=' + item.shop_id} className={styles.aiCard}>
                <span className={styles.rank}>{index + 1}</span>
                <div className={styles.resultMain}>
                  <div className={styles.productTitle}>{item.product_name}</div>
                  <div className={styles.shopName}>{item.shop_name}</div>
                  <div className={styles.meta}>
                    <span className={styles.rating}><Star size={14} fill="currentColor" /> {item.rating_count ? item.rating : 'New'}</span>
                    <span>{item.rating_count ? item.rating_count + ' reviews' : 'No ratings yet'}</span>
                  </div>
                </div>
                <div className={styles.price}>₹{Number(item.price || 0).toFixed(2)}</div>
              </Link>
            ))}
            {!ai.length ? <div className={styles.empty}>No matching products in enabled shops.</div> : null}
          </div>
        </section>
      ) : query.trim() ? (
        <section className={styles.content}>
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <span className={styles.sectionEyebrow}>SHOP DISCOVERY</span>
                <h2>Shops</h2>
              </div>
              <span className={styles.count}>{shops.length}</span>
            </div>
            <div className={styles.shopGrid}>
              {shops.map((shop) => (
                <Link key={shop.shop_id} href={'/?shop_id=' + shop.shop_id} className={styles.shopCard}>
                  <div className={styles.shopIcon}><Store size={23} /></div>
                  <div className={styles.shopNameLarge}>{shop.shop_name}</div>
                  <div className={styles.shopAddress}>{shop.city || shop.address || 'Online shop'}</div>
                  <div className={styles.meta}>
                    <span className={styles.rating}><Star size={14} fill="currentColor" /> {shop.rating_count ? shop.rating : 'New'}</span>
                    <span>{shop.rating_count ? shop.rating_count + ' reviews' : 'New shop'}</span>
                  </div>
                  <div className={styles.openLink}>Open shop <ArrowRight size={15} /></div>
                </Link>
              ))}
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div>
                <span className={styles.sectionEyebrow}>PRICE COMPARISON</span>
                <h2>Products across shops</h2>
              </div>
              <span className={styles.count}>{products.length}</span>
            </div>
            <div className={styles.list}>
              {products.map((product) => (
                <Link key={String(product.product_id) + '-' + String(product.shop_id)} href={'/?shop_id=' + product.shop_id} className={styles.productCard}>
                  <div className={styles.productIcon}><ShoppingBag size={20} /></div>
                  <div className={styles.resultMain}>
                    <div className={styles.productTitle}>{product.product_name}</div>
                    <div className={styles.shopName}>{product.shop_name}</div>
                    <div className={styles.meta}>
                      <span className={styles.rating}><Star size={14} fill="currentColor" /> {product.rating_count ? product.rating : 'New'}</span>
                      <span>{product.stock_available > 0 ? 'In stock' : 'Out of stock'}</span>
                    </div>
                  </div>
                  <div className={styles.price}>₹{Number(product.price || 0).toFixed(2)}</div>
                </Link>
              ))}
              {!products.length ? <div className={styles.empty}>No product matches found across enabled shops.</div> : null}
            </div>
          </section>
        </section>
      ) : (
        <section className={styles.section}>
          <div className={styles.sectionHeader}>
            <div>
              <span className={styles.sectionEyebrow}>DISCOVER</span>
              <h2>Online shops near you</h2>
            </div>
            <span className={styles.count}>{shops.length} shops</span>
          </div>
          <div className={styles.shopGrid}>
            {shops.map((shop) => (
              <Link key={shop.shop_id} href={'/?shop_id=' + shop.shop_id} className={styles.shopCard}>
                <div className={styles.shopIcon}><Store size={23} /></div>
                <div className={styles.shopNameLarge}>{shop.shop_name}</div>
                <div className={styles.shopAddress}>{shop.city || shop.address || 'Online shop'}</div>
                <div className={styles.meta}>
                  <span className={styles.rating}><Star size={14} fill="currentColor" /> {shop.rating_count ? shop.rating : 'New'}</span>
                  <span>{shop.rating_count ? shop.rating_count + ' reviews' : 'New shop'}</span>
                </div>
                <div className={styles.openLink}>Open shop <ArrowRight size={15} /></div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
