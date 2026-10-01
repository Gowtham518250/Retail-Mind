'use client';

import { useState } from 'react';
import {
  ArrowRight, Bot, CheckCircle2, ChevronRight, MapPin, PackageSearch,
  Search, ShoppingBag, Star, Store, Sparkles, SlidersHorizontal,
} from 'lucide-react';
import Link from 'next/link';
import { API_BASE } from '../../lib/api';
import styles from './page.module.css';

type Recommendation = {
  product_id: number;
  product_name: string;
  description?: string;
  price: number;
  stock_available: number;
  shop_id: number;
  shop_name: string;
  shop_tagline?: string;
  shop_address?: string;
  rating: number;
  rating_count: number;
  online_setup_fee?: number;
  reason?: string;
};

const examples = [
  'low price rice',
  'best rated atta',
  'milk under ₹80',
  'low price rice at Ganesh Store',
  'best rated shampoo under ₹500',
  'find Redmi phone under ₹15000',
];

export default function AiShoppingPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [available, setAvailable] = useState<boolean | null>(null);
  const [results, setResults] = useState<Recommendation[]>([]);
  const [intent, setIntent] = useState('');
  const [productQuery, setProductQuery] = useState('');
  const [shopHint, setShopHint] = useState('');
  const [error, setError] = useState('');
  const [recent, setRecent] = useState<string[]>([]);

  async function ask(nextQuery?: string) {
    const value = (nextQuery ?? query).trim();
    if (value.length < 2 || loading) return;

    setQuery(value);
    setLoading(true);
    setError('');
    setMessage('');
    setAvailable(null);
    setResults([]);

    try {
      const res = await fetch(
        API_BASE + '/store/customer-ai?q=' + encodeURIComponent(value) + '&limit=10',
        { cache: 'no-store' },
      );
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data?.detail || 'Shopping AI is temporarily unavailable.');
      }

      setAvailable(data.available === true);
      setMessage(data.message || '');
      setIntent(data.intent_label || '');
      setProductQuery(data.product_query || value);
      setShopHint(data.shop_hint || '');
      setResults(Array.isArray(data.recommendations) ? data.recommendations : []);

      if (data.available === true) {
        setRecent((current) => [value, ...current.filter((item) => item !== value)].slice(0, 6));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Shopping AI is temporarily unavailable.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <section className={styles.hero}>
        <div className={styles.heroGlowOne} />
        <div className={styles.heroGlowTwo} />

        <div className={styles.heroTop}>
          <Link href="/" className={styles.backLink}>
            <ChevronRight size={15} className={styles.backChevron} />
            Marketplace
          </Link>
          <div className={styles.liveBadge}>
            <span className={styles.liveDot} />
            LIVE STORE DATA
          </div>
        </div>

        <div className={styles.heroGrid}>
          <div className={styles.heroCopy}>
            <div className={styles.eyebrow}>
              <Sparkles size={14} />
              RETAIL MIND AI SHOPPING
            </div>
            <h1>
              Tell us what you need.
              <span> We compare the real shops.</span>
            </h1>
            <p>
              Ask naturally about price, rating, budget or a specific shop.
              Recommendations come only from products currently listed by
              online-enabled shops.
            </p>

            <div className={styles.searchShell}>
              <Search size={21} />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void ask();
                }}
                placeholder="Try low price rice or best rated atta under ₹500…"
                aria-label="Ask Retail Mind AI"
              />
              <button onClick={() => void ask()} disabled={loading}>
                {loading ? <span className={styles.spinner} /> : <Bot size={17} />}
                {loading ? 'Thinking…' : 'Ask AI'}
              </button>
            </div>

            <div className={styles.exampleRow}>
              {examples.map((example) => (
                <button key={example} onClick={() => void ask(example)}>
                  {example}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.orbitalVisual} aria-hidden="true">
            <div className={styles.orbit + ' ' + styles.orbitA} />
            <div className={styles.orbit + ' ' + styles.orbitB} />
            <div className={styles.aiCore}>
              <Bot size={39} />
            </div>
            <div className={styles.floatCard + ' ' + styles.floatOne}>
              <PackageSearch size={18} />
              <div><strong>Real inventory</strong><span>Only products that exist</span></div>
            </div>
            <div className={styles.floatCard + ' ' + styles.floatTwo}>
              <Star size={17} fill="currentColor" />
              <div><strong>Compare ratings</strong><span>Shop reputation included</span></div>
            </div>
            <div className={styles.floatCard + ' ' + styles.floatThree}>
              <ShoppingBag size={17} />
              <div><strong>Open &amp; order</strong><span>Go straight to the shop</span></div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.workspace}>
        {recent.length > 0 && (
          <div className={styles.recentBar}>
            <span>Recent questions</span>
            {recent.map((item) => (
              <button key={item} onClick={() => void ask(item)}>{item}</button>
            ))}
          </div>
        )}

        {error && (
          <div className={styles.errorCard}>
            <div className={styles.stateIcon}><Bot size={22} /></div>
            <div><strong>Shopping AI unavailable</strong><p>{error}</p></div>
          </div>
        )}

        {!loading && available === false && !error && (
          <section className={styles.unavailableCard}>
            <div className={styles.unavailableVisual}>
              <PackageSearch size={34} />
              <span>0</span>
            </div>
            <div>
              <div className={styles.stateEyebrow}>NO VERIFIED MATCH</div>
              <h2>Product unavailable</h2>
              <p>{message}</p>
              <div className={styles.tipRow}>
                <span><CheckCircle2 size={15} /> Try another product name</span>
                <span><CheckCircle2 size={15} /> Remove a tight budget</span>
                <span><CheckCircle2 size={15} /> Try another shop</span>
              </div>
            </div>
          </section>
        )}

        {!loading && available === true && !error && (
          <>
            <div className={styles.answerCard}>
              <div className={styles.answerIcon}><Bot size={21} /></div>
              <div className={styles.answerBody}>
                <div className={styles.answerTop}>
                  <span className={styles.answerLabel}>AI ANSWER</span>
                  {intent && <span className={styles.intentBadge}><SlidersHorizontal size={12} /> {intent}</span>}
                </div>
                <h2>{message}</h2>
                <div className={styles.answerMeta}>
                  {productQuery && <span><PackageSearch size={14} /> {productQuery}</span>}
                  {shopHint && <span><Store size={14} /> {shopHint}</span>}
                </div>
              </div>
            </div>

            <div className={styles.resultHeader}>
              <div>
                <span className={styles.stateEyebrow}>VERIFIED MATCHES</span>
                <h2>{results.length} real product option{results.length === 1 ? '' : 's'}</h2>
              </div>
              <span className={styles.liveResult}><span className={styles.liveDot} /> Stock-aware</span>
            </div>

            <div className={styles.resultGrid}>
              {results.map((item, index) => (
                <article
                  className={styles.resultCard}
                  key={String(item.product_id) + '-' + String(item.shop_id)}
                >
                  <div className={styles.rank}>{index + 1}</div>
                  <div className={styles.resultTop}>
                    <div className={styles.productIcon}><PackageSearch size={21} /></div>
                    <div className={styles.price}>₹{Number(item.price).toFixed(2)}</div>
                  </div>

                  <h3>{item.product_name}</h3>
                  <p className={styles.description}>
                    {item.description || item.reason || 'Available for online ordering.'}
                  </p>

                  <div className={styles.shopPanel}>
                    <div className={styles.shopIcon}><Store size={17} /></div>
                    <div>
                      <strong>{item.shop_name}</strong>
                      <span>{item.shop_tagline || 'Online-enabled shop'}</span>
                    </div>
                  </div>

                  <div className={styles.detailGrid}>
                    <div>
                      <span>Rating</span>
                      <strong><Star size={14} fill="currentColor" /> {item.rating > 0 ? item.rating.toFixed(1) : 'New'}</strong>
                    </div>
                    <div>
                      <span>Reviews</span>
                      <strong>{item.rating_count || 0}</strong>
                    </div>
                    <div>
                      <span>Stock</span>
                      <strong className={item.stock_available > 0 ? styles.stockGood : styles.stockBad}>
                        {item.stock_available > 0 ? String(item.stock_available) + ' available' : 'Unavailable'}
                      </strong>
                    </div>
                  </div>

                  {item.shop_address && (
                    <div className={styles.address}>
                      <MapPin size={13} /><span>{item.shop_address}</span>
                    </div>
                  )}

                  {Number(item.online_setup_fee || 0) > 0 && (
                    <div className={styles.feeNotice}>
                      Online setup fee ₹{Number(item.online_setup_fee).toFixed(2)} per order
                    </div>
                  )}

                  <div className={styles.actions}>
                    <Link
                      href={'/shop/' + item.shop_id + '/product/' + item.product_id}
                      className={styles.secondaryButton}
                    >
                      Product details
                    </Link>
                    <Link href={'/shop/' + item.shop_id} className={styles.primaryButton}>
                      Open shop <ArrowRight size={15} />
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        {!loading && available === null && !error && (
          <section className={styles.startCard}>
            <div className={styles.startVisual}>
              <div className={styles.startCube}><Bot size={31} /></div>
            </div>
            <div>
              <div className={styles.stateEyebrow}>HOW IT WORKS</div>
              <h2>Ask one simple question.</h2>
              <p>
                Retail Mind checks online-enabled shops, matches the product,
                applies your price/rating preference, and shows the actual
                shop where you can continue shopping.
              </p>
              <div className={styles.workflow}>
                <span><Search size={14} /> Understand</span>
                <ArrowRight size={13} />
                <span><PackageSearch size={14} /> Verify stock</span>
                <ArrowRight size={13} />
                <span><Star size={14} /> Compare</span>
                <ArrowRight size={13} />
                <span><ShoppingBag size={14} /> Order</span>
              </div>
            </div>
          </section>
        )}
      </section>
    </main>
  );
}
