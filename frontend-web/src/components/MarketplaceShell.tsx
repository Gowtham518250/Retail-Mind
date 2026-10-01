'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Search, Sparkles, Store, ShoppingBag, Star, ArrowRight, Bot, Boxes, Truck, Zap, MapPin } from 'lucide-react';
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
      const res = await fetch(
        API_BASE + '/store/marketplace/search?mode=shops&limit=60',
        { cache: 'no-store' },
      );
      const data = await res.json();
      setShops(data.shops || []);
      setProducts([]);
      setAi([]);
      setAiMessage('');
    } finally {
      setLoading(false);
    }
  };

  const runSearch = async (overrideMode?: ResultMode) => {
    const value = query.trim();
    const activeMode = overrideMode ?? mode;
    if (!value) {
      await loadShops();
      return;
    }

    setSearching(true);
    try {
      if (activeMode === 'ai') {
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
        const searchMode = activeMode === 'shops' ? 'shops' : activeMode === 'products' ? 'products' : 'all';
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
        <div className={styles.heroMesh} />
        <div className={styles.heroOrbOne} />
        <div className={styles.heroOrbTwo} />

        <div className={styles.heroTop}>
          <span className={styles.heroEyebrow}>
            <Sparkles size={13} /> RETAIL MIND MARKETPLACE
          </span>
          <span className={styles.livePill}>
            <span className={styles.liveDot} /> Online shops only
          </span>
        </div>

        <div className={styles.heroGrid}>
          <div className={styles.heroCopy}>
            <div className={styles.heroKicker}>YOUR LOCAL SHOPS, NOW ONLINE</div>
            <h1>
              Shop local.
              <span> Compare smarter.</span>
              Order simply.
            </h1>
            <p>
              Find a shop by name, compare one product across multiple shops,
              or ask the shopping assistant for low-price and highly-rated options.
            </p>

            <div className={styles.searchShell}>
              <Search size={20} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void runSearch();
                }}
                placeholder="Search a shop or product…"
              />
              <button onClick={() => void runSearch()} disabled={searching}>
                {searching ? 'Searching…' : 'Search'} <ArrowRight size={15} />
              </button>
            </div>

            <div className={styles.modeRow}>
              {[
                ['all', 'Everything'],
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
                  {value === 'ai' ? <Bot size={14} /> : null}
                  {label}
                </button>
              ))}
            </div>

            <div className={styles.heroTrustRow}>
              <span><ShieldCheckIcon /> Secure checkout</span>
              <span><Truck size={14} /> Order tracking</span>
              <span><Zap size={14} /> Smart recommendations</span>
            </div>
          </div>

          <div className={styles.sceneWrap} aria-hidden="true">
            <div className={styles.scene}>
              <div className={styles.sceneGlow} />

              <div className={styles.backShelf}>
                <div />
                <div />
                <div />
              </div>

              <div className={styles.store3d}>
                <div className={styles.storeRoof} />
                <div className={styles.storeFace}>
                  <div className={styles.storeSign}><Store size={14} /> RETAIL SHOP</div>
                  <div className={styles.storeShelfRow}><span /><span /><span /><span /></div>
                  <div className={styles.storeShelfRow compact}><span /><span /><span /></div>
                  <div className={styles.storeDoor} />
                </div>
                <div className={styles.storeFloor} />
              </div>

              <div className={styles.floatCardOne}>
                <div className={styles.miniIcon}><ShoppingBag size={16} /></div>
                <div><strong>Fresh groceries</strong><span>From nearby shops</span></div>
              </div>

              <div className={styles.floatCardTwo}>
                <div className={styles.miniIconGold}><Star size={15} fill="currentColor" /></div>
                <div><strong>4.8 rated</strong><span>Trusted local store</span></div>
              </div>

              <div className={styles.productBoxRed}>
                <div className={styles.boxTop} />
                <div className={styles.boxFront}><span>BEST</span><strong>DEAL</strong></div>
                <div className={styles.boxSide} />
              </div>

              <div className={styles.productBoxBlue}>
                <div className={styles.boxTop} />
                <div className={styles.boxFront}><span>SMART</span><strong>PICK</strong></div>
                <div className={styles.boxSide} />
              </div>

              <div className={styles.sceneBase}><div /></div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.quickRow}>
        <div><span><Store size={17} /></span><div><strong>Local shops</strong><small>Discover online-enabled stores</small></div></div>
        <div><span><Boxes size={17} /></span><div><strong>Compare products</strong><small>See offers across shops</small></div></div>
        <div><span><Bot size={17} /></span><div><strong>Ask Retail Mind</strong><small>Get price & rating advice</small></div></div>
        <div><span><Truck size={17} /></span><div><strong>Track orders</strong><small>Follow the order lifecycle</small></div></div>
      </section>

      <section className={styles.exploreStrip}>
        <div>
          <span className={styles.sectionEyebrow}>SHOP SMARTER</span>
          <h2>Search a shop. Compare a product. Let AI help.</h2>
        </div>
        <div className={styles.explorePills}>
          <button onClick={() => { setQuery('Groceries'); setMode('products'); void runSearch('products'); }}>🛒 Groceries</button>
          <button onClick={() => { setQuery('Bakery'); setMode('products'); void runSearch('products'); }}>🥖 Bakery</button>
          <button onClick={() => { setQuery('Personal care'); setMode('products'); void runSearch('products'); }}>✨ Personal care</button>
          <button onClick={() => { setMode('ai'); setQuery('best rated products'); void runSearch('ai'); }}><Sparkles size={13} /> Best value with AI</button>
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
              <Link key={item.product_id} href={'/shop/' + item.shop_id} className={styles.aiCard}>
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
                <Link key={shop.shop_id} href={'/shop/' + shop.shop_id} className={styles.shopCard}>
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
                <Link key={String(product.product_id) + '-' + String(product.shop_id)} href={'/shop/' + product.shop_id} className={styles.productCard}>
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
              <h2>Discover online shops</h2>
            </div>
            <span className={styles.count}>{shops.length} shops</span>
          </div>
          <div className={styles.shopGrid}>
            {shops.map((shop) => (
              <Link key={shop.shop_id} href={'/shop/' + shop.shop_id} className={styles.shopCard}>
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


function ShieldCheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 3 5 6v5c0 4.6 2.9 8.5 7 10 4.1-1.5 7-5.4 7-10V6l-7-3Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m9.2 12 1.8 1.8 3.8-4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
