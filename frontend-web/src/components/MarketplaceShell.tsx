'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Bot, Boxes, MapPin, Search, ShieldCheck, Sparkles, Star, Store, Truck, Zap } from 'lucide-react';
import styles from './MarketplaceShell.module.css';
import { API_BASE } from '../lib/api';
import ThreeDRetailScene from './ThreeDRetailScene';

type ResultMode = 'all' | 'shops' | 'products';

export default function MarketplaceShell() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>('all');
  const [shops, setShops] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [aiMessage, setAiMessage] = useState('');
  const [aiResults, setAiResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

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
        const res = await fetch(API_BASE + '/store/marketplace/search?mode=shops&limit=60', { cache: 'no-store', signal: controller.signal });
        if (!res.ok) throw new Error('Marketplace API returned ' + res.status + '.');
        const data = await res.json();
        if (requestId !== requestIdRef.current) return;
        setShops(Array.isArray(data.shops) ? data.shops : []);
        setProducts([]);
        return;
      }

      const searchMode = requestedMode === 'shops' ? 'shops' : requestedMode === 'products' ? 'products' : 'all';
      const res = await fetch(
        API_BASE + '/store/marketplace/search?q=' + encodeURIComponent(value) + '&mode=' + searchMode + '&limit=30',
        { cache: 'no-store', signal: controller.signal }
      );
      if (!res.ok) throw new Error('Marketplace API returned ' + res.status + '.');
      const data = await res.json();
      if (requestId !== requestIdRef.current) return;

      setShops(Array.isArray(data.shops) ? data.shops : []);
      setProducts(Array.isArray(data.products) ? data.products : []);
    } catch (err) {
      if (controller.signal.aborted || requestId !== requestIdRef.current) return;
      setShops([]);
      setProducts([]);
      setError(err instanceof Error ? err.message : 'Unable to search the marketplace.');
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
    void performSearch('all', '');
    return () => {
      requestIdRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  const preset = (value: string) => {
    setQuery(value);
    setMode('products');
    void performSearch('products', value, true);
  };

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroGridLines} />
        <div className={styles.heroGlow} />
        <div className={styles.heroContent}>
          <div className={styles.heroEyebrow}><span className={styles.statusDot} /> RETAIL MIND · LOCAL COMMERCE, REIMAGINED</div>
          <div className={styles.heroCopy}>
            <div className={styles.heroKicker}>YOUR NEIGHBOURHOOD, NOW ONLINE</div>
            <h1>Shop local.<span>Think smarter.</span><em>Move faster.</em></h1>
            <p>Discover online-enabled shops, compare products across stores, and use AI to find the right value — all from one beautifully connected marketplace.</p>
          </div>

          <div className={styles.searchPanel}>
            <Search size={19} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => {
              if (event.key === 'Enter') void performSearch(mode, query, true);
            }} placeholder="Search products, shops or categories" aria-label="Search products, shops or categories" />
            <button onClick={() => void performSearch(mode, query, true)} disabled={searching}>
              {searching ? 'Finding…' : 'Explore'} <ArrowRight size={15} />
            </button>
          </div>

          <div className={styles.modeRow}>
            <button className={mode === 'all' ? styles.modeActive : styles.mode} onClick={() => { setMode('all'); void performSearch('all', query, true); }}>Everything</button>
            <button className={mode === 'shops' ? styles.modeActive : styles.mode} onClick={() => { setMode('shops'); void performSearch('shops', query, true); }}><Store size={14} /> Shops</button>
            <button className={mode === 'products' ? styles.modeActive : styles.mode} onClick={() => { setMode('products'); void performSearch('products', query, true); }}><Boxes size={14} /> Products</button>
            <button className={styles.modeAi} onClick={performAiSearch}><Bot size={14} /> Ask AI</button>
          </div>

          <div className={styles.heroTrustRow}>
            <span><ShieldCheck size={14} /><b>Secure checkout</b><small>Protected ordering</small></span>
            <span><Truck size={14} /><b>Fast fulfilment</b><small>Local dispatch</small></span>
            <span><Zap size={14} /><b>Live availability</b><small>Stock-aware</small></span>
          </div>
        </div>

        <ThreeDRetailScene />
      </section>

      <section className={styles.featureRail}>
        <button className={styles.featureRailItem} onClick={() => { setMode('shops'); void performSearch('shops', '', true); }}>
          <span className={styles.featureIcon}><Store size={18} /></span>
          <div><strong>Local storefronts</strong><small>Meet verified shops near you</small></div>
          <ArrowRight size={15} />
        </button>
        <button className={styles.featureRailItem} onClick={() => { setMode('products'); void performSearch('products', '', true); }}>
          <span className={styles.featureIcon}><Boxes size={18} /></span>
          <div><strong>Compare products</strong><small>See prices across stores</small></div>
          <ArrowRight size={15} />
        </button>
        <button className={styles.featureRailItem} onClick={() => router.push('/ai-shopping')}>
          <span className={styles.featureIcon}><Sparkles size={18} /></span>
          <div><strong>AI shopping</strong><small>Describe what you need</small></div>
          <ArrowRight size={15} />
        </button>
        <Link href="/orders" className={styles.featureRailItem}>
          <span className={styles.featureIcon}><Truck size={18} /></span>
          <div><strong>Order centre</strong><small>Returns, reviews & history</small></div>
          <ArrowRight size={15} />
        </Link>
      </section>

      <section className={styles.discoveryBar}>
        <div className={styles.discoveryCopy}>
          <div className={styles.sectionEyebrow}>QUICK DISCOVERY</div>
          <h2>Jump into a shopping mood.</h2>
          <p>Pick a category, or let Retail Mind turn a sentence into a shortlist.</p>
        </div>
        <div className={styles.presetRow}>
          <button onClick={() => preset('Groceries')}><span>01</span><b>Groceries</b><small>Everyday essentials</small></button>
          <button onClick={() => preset('Bakery')}><span>02</span><b>Bakery</b><small>Freshly baked</small></button>
          <button onClick={() => preset('Personal care')}><span>03</span><b>Personal care</b><small>Beauty & wellness</small></button>
          <button className={styles.presetAi} onClick={() => router.push('/ai-shopping')}><Sparkles size={14} /><b>Find with AI</b><small>Ask naturally</small></button>
        </div>
      </section>

      {error && <section className={styles.banner} role="alert"><div className={styles.bannerIcon}>!</div><div><strong>Marketplace connection issue</strong><p>{error}</p></div></section>}
      {aiMessage && <section className={styles.aiBanner}><div className={styles.aiBannerIcon}><Sparkles size={17} /></div><div><strong>Retail Mind AI</strong><p>{aiMessage}</p></div></section>}

      {loading ? (
        <section className={styles.resultsSection}>
          <div className={styles.sectionHeader}><div><div className={styles.sectionEyebrow}>DISCOVER</div><h2>Loading nearby shops</h2></div></div>
          <div className={styles.shopGrid}>{Array.from({ length: 8 }).map((_, index) => <div className={styles.skeletonCard} key={index} />)}</div>
        </section>
      ) : aiResults.length ? (
        <section className={styles.resultsSection}>
          <div className={styles.sectionHeader}><div><div className={styles.sectionEyebrow}>AI CURATED</div><h2>Recommended for you</h2></div><span className={styles.count}>{aiResults.length} picks</span></div>
          <div className={styles.list}>
            {aiResults.map((item, index) => (
              <Link key={String(item.product_id) + '-' + String(item.shop_id) + '-' + String(index)} href={'/shop/' + item.shop_id} className={styles.resultCard}>
                <span className={styles.rank}>{index + 1}</span>
                <div className={styles.resultMain}><strong>{item.product_name}</strong><span>{item.shop_name}</span><small><Star size={12} fill="currentColor" /> {item.rating_count ? item.rating : 'New'} · {item.rating_count || 0} reviews</small></div>
                <div className={styles.resultPrice}>₹{Number(item.price || 0).toFixed(2)}</div>
              </Link>
            ))}
          </div>
        </section>
      ) : query.trim() ? (
        <section className={styles.resultsSection}>
          <div className={styles.sectionHeader}><div><div className={styles.sectionEyebrow}>RESULTS</div><h2>{mode === 'shops' ? 'Shops matching your search' : mode === 'products' ? 'Products matching your search' : 'Shops and products'}</h2></div></div>

          {mode !== 'products' && (
            <div className={styles.shopGrid}>
              {shops.map((shop) => (
                <Link key={shop.shop_id} href={'/shop/' + shop.shop_id} className={styles.shopCard}>
                  <div className={styles.shopCover}>
                    {shop.logo_url ? (
                      <img
                        src={
                          shop.logo_url.startsWith('http')
                            ? shop.logo_url
                            : API_BASE + shop.logo_url
                        }
                        alt={shop.shop_name + ' logo'}
                      />
                    ) : (
                      <div className={styles.shopLogoFallback}><Store size={24} /></div>
                    )}
                    <span className={styles.shopStatus}><i /> Online</span>
                  </div>
                  <div className={styles.shopCardBody}>
                    <div className={styles.shopCardTopline}>
                      <span>{shop.shop_type || 'Local store'}</span>
                      <div><Star size={12} fill="currentColor" /> {shop.rating_count ? Number(shop.rating).toFixed(1) : 'New'}</div>
                    </div>
                    <strong>{shop.shop_name}</strong>
                    <p>{shop.tagline || shop.description || 'A trusted neighbourhood shop, now available online.'}</p>
                    <div className={styles.shopCardMeta}>
                      <span><MapPin size={12} /> {shop.city || shop.address || 'Local delivery'}</span>
                      <span>{shop.rating_count || 0} reviews</span>
                    </div>
                  </div>
                  <div className={styles.shopCardArrow}><ArrowRight size={17} /></div>
                </Link>
              ))}
            </div>
          )}

          {mode !== 'shops' && (
            <div className={styles.list}>
              {products.map((product) => (
                <Link key={String(product.product_id) + '-' + String(product.shop_id)} href={'/shop/' + product.shop_id + '/product/' + product.product_id} className={styles.resultCard}>
                  <span className={styles.productMark}><Boxes size={17} /></span>
                  <div className={styles.resultMain}><strong>{product.product_name}</strong><span>{product.shop_name}</span><small><Star size={12} fill="currentColor" /> {product.rating_count ? product.rating : 'New'} · {product.stock_available > 0 ? 'In stock' : 'Out of stock'}</small></div>
                  <div className={styles.resultPrice}>₹{Number(product.price || 0).toFixed(2)}</div>
                </Link>
              ))}
            </div>
          )}

          {!shops.length && !products.length && <div className={styles.emptyState}><div className={styles.emptyIcon}><Search size={22} /></div><strong>No matches yet</strong><p>Try a broader shop, category or product keyword.</p></div>}
        </section>
      ) : (
        <section className={styles.resultsSection}>
          <div className={styles.sectionHeader}><div><div className={styles.sectionEyebrow}>DISCOVER</div><h2>Online shops worth exploring</h2></div><span className={styles.count}>{shops.length} shops</span></div>
          <div className={styles.shopGrid}>
            {shops.map((shop) => (
              <Link key={shop.shop_id} href={'/shop/' + shop.shop_id} className={styles.shopCard}>
                <div className={styles.shopIcon}><Store size={20} /></div>
                <div className={styles.shopCardBody}><strong>{shop.shop_name}</strong><span>{shop.city || shop.address || 'Online shop'}</span><small><Star size={12} fill="currentColor" /> {shop.rating_count ? shop.rating : 'New'} · {shop.rating_count || 0} reviews</small></div>
                <ArrowRight size={17} />
              </Link>
            ))}
          </div>
          {!shops.length && <div className={styles.emptyState}><div className={styles.emptyIcon}><Store size={22} /></div><strong>No online shops are showing right now</strong><p>Try refreshing or opening a shop link directly.</p></div>}
        </section>
      )}
    </main>
  );
}
