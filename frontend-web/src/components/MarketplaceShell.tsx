'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowRight, Bot, Boxes, MapPin, Search, ShieldCheck, Sparkles, Star, Store, Truck, Zap } from 'lucide-react';
import styles from './MarketplaceShell.module.css';
import { API_BASE } from '../lib/api';
import ThreeDRetailScene from './ThreeDRetailScene';

type ResultMode = 'all' | 'shops' | 'products';
type FeaturedProduct = { product_id: number; product_name: string; shop_id: number; shop_name: string; price: number; image_url?: string | null; category?: string; description?: string; stock_available?: number };

export default function MarketplaceShell() {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<ResultMode>('all');
  const [shops, setShops] = useState<any[]>([]);
  const [products, setProducts] = useState<any[]>([]);
  const [featuredProducts, setFeaturedProducts] = useState<FeaturedProduct[]>([]);
  const [activeProductCategory, setActiveProductCategory] = useState('All');
  const [aiMessage, setAiMessage] = useState('');
  const [aiResults, setAiResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const requestIdRef = useRef(0);
  const controllerRef = useRef<AbortController | null>(null);

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
          const response = await fetch(API_BASE + '/store/shops/' + encodeURIComponent(String(shop.shop_id)) + '/products', { cache: 'no-store' });
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

  useEffect(() => {
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

  return (
    <main className={styles.page}>
      <section className={styles.hero} data-retail-hero>
        <div className={styles.heroGridLines} />
        <div className={styles.heroGlow} />
        <div className={styles.heroArtwork} aria-hidden="true">
          <div className={styles.heroPaint + ' ' + styles.heroPaintGold} />
          <div className={styles.heroPaint + ' ' + styles.heroPaintMint} />
          <div className={styles.heroProductWall}>
            {showcaseProducts.length ? (
              [0, 1].map((row) => (
                <div key={row} className={styles.heroProductRow} data-product-row={row}>
                  {showcaseProducts.slice(row * 3, row * 3 + 3).map((product) => (
                    <div key={product.shop_id + '-' + product.product_id} className={styles.heroProductBottle}>
                      {product.image_url ? (
                        <img src={product.image_url} alt="" loading="lazy" onError={(event) => { event.currentTarget.style.visibility = 'hidden'; }} />
                      ) : (
                        <div className={styles.heroProductPlaceholder}><Boxes size={30} strokeWidth={1.4} /></div>
                      )}
                      <span>{product.product_name}</span>
                    </div>
                  ))}
                </div>
              ))
            ) : shops.length ? (
              [0, 1].map((row) => (
                <div key={row} className={styles.heroProductRow + ' ' + styles.heroShopRow} data-product-row={row}>
                  {shops.slice(row * 3, row * 3 + 3).map((shop) => (
                    <div key={shop.shop_id} className={styles.heroShopTile}>
                      <div className={styles.heroShopArtwork}>
                        {shop.logo_url ? (
                          <img
                            src={shop.logo_url.startsWith('http') ? shop.logo_url : API_BASE + shop.logo_url}
                            alt=""
                            loading="lazy"
                          />
                        ) : (
                          <Store size={38} strokeWidth={1.5} />
                        )}
                      </div>
                      <span>{shop.shop_name}</span>
                      <small>{shop.city || shop.shop_type || 'LOCAL STORE'}</small>
                    </div>
                  ))}
                </div>
              ))
            ) : (
              <ThreeDRetailScene />
            )}
          </div>
          <div className={styles.heroOrbit} />
          <div className={styles.heroChalkboard}>
            <span>LOCAL MARKETPLACE</span>
            <strong>Shop small.</strong>
            <strong>Find more.</strong>
            <small>Everyday value, nearby.</small>
          </div>
          <div className={styles.heroFloatingStamp}><Store size={14} /><span>LOCAL STORES<br /><b>LIVE ONLINE</b></span></div>
        </div>
        <div className={styles.heroContent}>
          <div className={styles.heroEyebrow}><span className={styles.statusDot} /> RETAIL MIND · YOUR LOCAL MARKET</div>
          <div className={styles.heroCopy}>
            <div className={styles.heroKicker}>GOOD THINGS, CLOSER TO HOME</div>
            <h1><span className={styles.heroLine}>Shop local.</span><span className={styles.heroLineAccent}>Find more.</span><em>Shop smarter.</em></h1>
            <p>Discover trusted neighbourhood shops, compare real products and prices, and let Retail Mind help you find the right things closer to home.</p>
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
      </section>
      <section className={styles.pressTicker} aria-label="Retail Mind marketplace benefits">
        <div className={styles.pressTickerTrack}>
          {Array.from({length: 2}).map((_, run) => (
            <span className={styles.pressTickerRun} key={run}>
              {['LOCAL SHOPS · REAL PRICES','DISCOVER SOMETHING NEARBY','SMARTER EVERYDAY SHOPPING','SHOP LOCAL, LIVE BETTER'].map((item, index) => (
                <span className={styles.pressTickerItem} key={item + index}>{item}<b>✳</b></span>
              ))}
            </span>
          ))}
        </div>
      </section>

      <div className={styles.crateSlat} aria-hidden="true" />

      <section className={styles.categoryStage + ' ' + styles.revealSection} id="shop-by-mood" data-reveal-section>
        <div className={styles.categoryStageHead}>
          <div>
            <span className={styles.sectionEyebrow}>01 / SHOP BY CATEGORY</span>
            <h2>Find your kind<br />of <em>everyday.</em></h2>
            <p>Real products and neighbourhood shops, gathered in one place. Choose a category to see what’s available.</p>
          </div>
          <div className={styles.categoryStageNote}>
            <span>YOUR LOCAL MARKET</span>
            <strong>Good finds.<br />Closer to home.</strong>
            <small>Retail Mind · Local commerce</small>
          </div>
        </div>
        <div className={styles.categoryStageChips}>
          {discoveryCategories.map((category, index) => (
            <button
              type="button"
              key={category}
              className={styles.categoryStageChip}
              data-tone={index % 4}
              onClick={() => preset(category)}
            >
              <span>0{index + 1}</span><strong>{category}</strong><ArrowRight size={16} />
            </button>
          ))}
          <button type="button" className={styles.categoryStageChip + ' ' + styles.categoryStageChipAi} onClick={() => router.push('/ai-shopping')}>
            <span>✳</span><strong>Find with AI</strong><ArrowRight size={16} />
          </button>
        </div>
      </section>

      <section className={styles.crateSection + ' ' + styles.revealSection} id="build-your-list" data-reveal-section>
        <div className={styles.crateSectionLabel}><span>02 / YOUR SHOPPING LIST</span><i /></div>
        <div className={styles.crateSectionGrid}>
          <div className={styles.crateSectionCopy}>
            <span className={styles.sectionEyebrow}>PICK A STARTING POINT</span>
            <h2>Build a basket<br />from <em>your</em> neighbourhood.</h2>
            <p>Start with a kind of shop, browse real listings, then open a storefront to add the items you need.</p>
            <button type="button" className={styles.cratePrimaryButton} onClick={() => { setQuery(''); setMode('shops'); void performSearch('shops', '', true); }}>
              Explore all shops <ArrowRight size={16} />
            </button>
          </div>
          <div className={styles.crateTiles}>
            {discoveryCategories.slice(0, 4).map((category, index) => (
              <button type="button" key={category} className={styles.crateTile} data-tone={index % 4} onClick={() => preset(category)}>
                <span className={styles.crateTileNumber}>0{index + 1}</span>
                <span className={styles.crateTileIcon}><Store size={20} /></span>
                <strong>{category}</strong>
                <small>Explore matching shops and products</small>
                <ArrowRight size={16} className={styles.crateTileArrow} />
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.featuredProductStage + ' ' + styles.revealSection} id="local-finds" data-reveal-section>
        <div className={styles.featuredProductHeader}>
          <div>
            <span className={styles.sectionEyebrow}>03 / FROM LOCAL SHELVES</span>
            <h2>Worth a closer<br /><em>look.</em></h2>
            <p>Product listings fetched from your real online-enabled shops.</p>
          </div>
          <div className={styles.featuredProductControls}>
            {productCategories.map((category) => (
              <button
                key={category}
                type="button"
                className={activeProductCategory === category ? styles.featuredCategoryActive : styles.featuredCategory}
                onClick={() => setActiveProductCategory(category)}
              >{category}</button>
            ))}
          </div>
        </div>
        {filteredFeaturedProducts.length ? (
          <div className={styles.featuredProductGrid}>
            {filteredFeaturedProducts.slice(0, 8).map((product, index) => (
              <Link
                key={product.shop_id + '-' + product.product_id}
                href={'/shop/' + product.shop_id + '/product/' + product.product_id}
                className={styles.featuredProductCard}
                style={{ animationDelay: (index * 70) + 'ms' }}
              >
                <div className={styles.featuredProductMedia} data-tone={index % 5}>
                  {product.image_url ? (
                    <img src={product.image_url} alt={product.product_name} loading="lazy" onError={(event) => { event.currentTarget.style.opacity = '0'; }} />
                  ) : (
                    <div className={styles.featuredProductPlaceholder}><Boxes size={46} strokeWidth={1.15} /><span>LOCAL PICK</span></div>
                  )}
                  <span className={styles.featuredProductIndex}>#{String(index + 1).padStart(2, '0')}</span>
                </div>
                <div className={styles.featuredProductBody}>
                  <span className={styles.featuredProductShop}>{product.shop_name}</span>
                  <strong>{product.product_name}</strong>
                  <div className={styles.featuredProductFoot}><b>₹{Number(product.price || 0).toFixed(2)}</b><span>View item <ArrowRight size={13} /></span></div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className={styles.featuredProductEmpty}>
            <span><Boxes size={25} /></span>
            <strong>{loading ? 'Finding products from local shops…' : shops.length ? 'Open a shop to discover its products' : 'Your local market is loading'}</strong>
            <p>Products will appear here when an online-enabled shop has items available in its storefront.</p>
            {shops.length > 0 && <Link href={'/shop/' + shops[0].shop_id}>Browse {shops[0].shop_name} <ArrowRight size={14} /></Link>}
          </div>
        )}
      </section>

      <section className={styles.localLedger + ' ' + styles.revealSection} id="how-it-works" data-reveal-section>
        <div className={styles.localLedgerIntro}>
          <span className={styles.sectionEyebrow}>04 / HOW IT WORKS</span>
          <h2>From nearby<br />to <em>at your door.</em></h2>
          <p>A simple path from finding a shop to placing and tracking an order.</p>
        </div>
        <div className={styles.localLedgerRows}>
          <div className={styles.localLedgerRow}><span>01</span><div><strong>Find a local shop</strong><small>Browse the shops that have enabled online ordering.</small></div><Store size={21} /></div>
          <div className={styles.localLedgerRow}><span>02</span><div><strong>Compare what you need</strong><small>Check product details and prices across available listings.</small></div><Boxes size={21} /></div>
          <div className={styles.localLedgerRow}><span>03</span><div><strong>Build your basket</strong><small>Add products from a storefront and review the checkout summary.</small></div><ArrowRight size={21} /></div>
          <div className={styles.localLedgerRow}><span>04</span><div><strong>Keep track of your order</strong><small>Open the order centre to follow order history and available actions.</small></div><Truck size={21} /></div>
        </div>
      </section>

      <section className={styles.chalkboardBenefits + ' ' + styles.revealSection} data-reveal-section>
        <div className={styles.chalkboardFrame}>
          <div className={styles.chalkboardHeading}>
            <span>RETAIL MIND · LOCAL COMMERCE</span>
            <h2>Small shops.<br /><em>Big convenience.</em></h2>
            <p>Everything you need to discover, compare, and shop local—with tools to make the search simpler.</p>
          </div>
          <div className={styles.chalkboardBenefitsGrid}>
            <div><span>01 / DISCOVER</span><strong>Your neighbourhood, online.</strong><small>Find local storefronts in one marketplace.</small></div>
            <div><span>02 / COMPARE</span><strong>Know before you go.</strong><small>See listed products and prices before opening a shop.</small></div>
            <div><span>03 / SHOP SMART</span><strong>Let AI help narrow it down.</strong><small>Describe what you need to get relevant product suggestions.</small></div>
          </div>
          <Link href="/ai-shopping" className={styles.chalkboardCta}>Find with Retail Mind AI <ArrowRight size={16} /></Link>
        </div>
      </section>

      {error && <section className={styles.banner} role="alert"><div className={styles.bannerIcon}>!</div><div><strong>Marketplace connection issue</strong><p>{error}</p></div></section>}
      {aiMessage && <section className={styles.aiBanner}><div className={styles.aiBannerIcon}><Sparkles size={17} /></div><div><strong>Retail Mind AI</strong><p>{aiMessage}</p></div></section>}

      {loading ? (
        <section className={styles.resultsSection + " " + styles.revealSection} data-reveal-section>
          <div className={styles.sectionHeader}><div><div className={styles.sectionEyebrow}>DISCOVER</div><h2>Loading nearby shops</h2></div></div>
          <div className={styles.shopGrid}>{Array.from({ length: 8 }).map((_, index) => <div className={styles.skeletonCard} key={index} />)}</div>
        </section>
      ) : aiResults.length ? (
        <section className={styles.resultsSection + " " + styles.revealSection} data-reveal-section>
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
        <section className={styles.resultsSection + " " + styles.revealSection} data-reveal-section>
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
        <section className={styles.resultsSection + " " + styles.revealSection} data-reveal-section>
          <div className={styles.sectionHeader}>
            <div>
              <div className={styles.sectionEyebrow}><Sparkles size={12} /> LOCAL STOREFRONTS</div>
              <h2>Find your next favourite shop</h2>
              <p className={styles.shopSectionSubtitle}>Meet the neighbourhood stores bringing everyday essentials closer to you.</p>
            </div>
            <span className={styles.count}>{shops.length} {shops.length === 1 ? 'shop' : 'shops'}</span>
          </div>
          <div className={styles.shopGrid}>
            {shops.map((shop, index) => (
              <Link
                key={shop.shop_id}
                href={'/shop/' + shop.shop_id}
                className={styles.shopCard}
                style={{ animationDelay: `${Math.min(index, 8) * 85}ms` }}
              >
                <div className={styles.shopVisual} aria-hidden="true">
                  <div className={styles.shopVisualOrb + ' ' + styles.shopVisualOrbOne} />
                  <div className={styles.shopVisualOrb + ' ' + styles.shopVisualOrbTwo} />
                  <div className={styles.shopVisualRing} />
                  <span className={styles.shopStatus}><i /> ONLINE STORE</span>
                  {shop.logo_url ? (
                    <div className={styles.shopLogoShowcase}>
                      <img
                        src={shop.logo_url.startsWith('http') ? shop.logo_url : API_BASE + shop.logo_url}
                        alt=""
                      />
                    </div>
                  ) : (
                    <div className={styles.shopIllustration}>
                      <div className={styles.shopStoreRoof} />
                      <div className={styles.shopStoreFront}>
                        <div className={styles.shopStoreSign}><Store size={12} /><span>LOCAL STORE</span></div>
                        <div className={styles.shopStoreWindows}><span /><span /></div>
                        <div className={styles.shopStoreDoor}><i /></div>
                      </div>
                    </div>
                  )}
                  <div className={styles.shopVisualSparkle}><Sparkles size={19} /></div>
                  <span className={styles.shopVisualLabel}>DISCOVER NEAR YOU</span>
                </div>
                <div className={styles.shopCardBody}>
                  <div className={styles.shopCardTopline}>
                    <span>{shop.shop_type || 'NEIGHBOURHOOD STORE'}</span>
                    <div><Star size={12} fill="currentColor" /> {shop.rating_count ? Number(shop.rating || 0).toFixed(1) : 'NEW'}</div>
                  </div>
                  <strong>{shop.shop_name}</strong>
                  <span className={styles.shopCardLocation}><MapPin size={13} /> {shop.city || shop.address || 'Local delivery'}</span>
                  <p>{shop.tagline || shop.description || 'A local favourite, ready when you are. Explore the shop and discover something useful.'}</p>
                  <div className={styles.shopCardMeta}>
                    <span>{shop.rating_count || 0} {Number(shop.rating_count || 0) === 1 ? 'review' : 'reviews'}</span>
                    <span className={styles.shopCardAvailability}><i /> Online ordering</span>
                  </div>
                  <div className={styles.shopCardFooter}>
                    <span>Explore storefront</span>
                    <span className={styles.shopCardFooterArrow}><ArrowRight size={15} /></span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
          {!shops.length && <div className={styles.emptyState}><div className={styles.emptyIcon}><Store size={22} /></div><strong>No online shops are showing right now</strong><p>Try refreshing or opening a shop link directly.</p></div>}
        </section>
      )}
      <footer className={styles.marketFooter}>
        <div className={styles.marketFooterBrand}><span className={styles.marketFooterStamp}>RM</span><strong>RETAIL MIND</strong><small>Good things, closer to home.</small></div>
        <div className={styles.marketFooterLinks}>
          <Link href="/ai-shopping">AI shopping</Link>
          <Link href="/orders">Order centre</Link>
          <button type="button" onClick={() => { window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Back to top ↑</button>
        </div>
        <p>Local shops. Real listings. Smarter everyday shopping.</p>
      </footer>
    </main>
  );
}
