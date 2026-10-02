'use client';

import { useState } from 'react';
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronLeft,
  Loader2,
  MapPin,
  Package,
  Search,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Star,
  Store,
  Zap,
} from 'lucide-react';
import Link from 'next/link';
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
  'low price ghee',
  'low price rice at Ganesh Store',
  'best rated shampoo under ₹500',
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
        '/api/ai-shopping?q=' +
          encodeURIComponent(value) +
          '&limit=10',
        { cache: 'no-store' },
      );

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail =
          typeof data?.detail === 'string'
            ? data.detail
            : typeof data?.message === 'string'
              ? data.message
              : `Shopping AI request failed (HTTP ${res.status}).`;
        throw new Error(detail);
      }

      setAvailable(data.available === true);
      setMessage(data.message || '');
      setIntent(data.intent_label || '');
      setProductQuery(data.product_query || value);
      setShopHint(data.shop_hint || '');
      setResults(Array.isArray(data.recommendations) ? data.recommendations : []);

      setRecent((current) =>
        [value, ...current.filter((item) => item !== value)].slice(0, 5),
      );
    } catch (err) {
      setAvailable(null);
      setResults([]);
      setError(
        err instanceof Error
          ? err.message
          : 'The shopping assistant is temporarily unavailable.',
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={`${styles.ambient} ${styles.ambientOne}`} />
      <div className={`${styles.ambient} ${styles.ambientTwo}`} />
      <div className={`${styles.ambient} ${styles.ambientThree}`} />

      <section className={styles.hero}>
        <div className={styles.navRow}>
          <Link href="/" className={styles.backLink}>
            <ChevronLeft size={15} />
            Marketplace
          </Link>

          <div className={styles.liveBadge}>
            <span className={styles.liveDot} />
            REAL STORE DATA
          </div>
        </div>

        <div className={styles.heroInner}>
          <div className={styles.copy}>
            <div className={styles.kicker}>
              <Sparkles size={13} />
              RETAIL MIND AI SHOPPING
            </div>

            <h1>
              Ask naturally.
              <span> Shop with confidence.</span>
            </h1>

            <p>
              Tell me the product, budget or shop you care about. I compare
              live inventory from shops that are actually enabled for online
              ordering.
            </p>

            <div className={styles.searchCard}>
              <div className={styles.searchIcon}>
                <Search size={19} />
              </div>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void ask();
                }}
                placeholder="Try “low price ghee”"
                aria-label="Ask Retail Mind AI"
              />
              <button
                className={styles.askButton}
                onClick={() => void ask()}
                disabled={loading || query.trim().length < 2}
              >
                {loading ? (
                  <>
                    <Loader2 size={16} className={styles.spin} />
                    Searching
                  </>
                ) : (
                  <>
                    <Zap size={15} />
                    Ask AI
                  </>
                )}
              </button>
            </div>

            <div className={styles.exampleStrip}>
              <span>Try:</span>
              {examples.slice(0, 4).map((example) => (
                <button key={example} onClick={() => void ask(example)}>
                  {example}
                </button>
              ))}
            </div>

            <div className={styles.trustRow}>
              <span><ShieldCheck size={14} /> Real inventory</span>
              <span><Star size={14} /> Rating-aware</span>
              <span><ShoppingBag size={14} /> Order from shop</span>
            </div>
          </div>

          <div className={styles.visual} aria-hidden="true">
            <div className={styles.visualHalo} />
            <div className={`${styles.visualOrbit} ${styles.orbitOne}`} />
            <div className={`${styles.visualOrbit} ${styles.orbitTwo}`} />
            <div className={styles.core}>
              <div className={styles.coreInner}>
                <Bot size={42} />
              </div>
            </div>

            <div className={`${styles.signal} ${styles.signalOne}`}>
              <Package size={16} />
              <div>
                <strong>Live inventory</strong>
                <span>Verified stock</span>
              </div>
            </div>

            <div className={`${styles.signal} ${styles.signalTwo}`}>
              <Star size={16} />
              <div>
                <strong>Compare ratings</strong>
                <span>Shop reputation</span>
              </div>
            </div>

            <div className={`${styles.signal} ${styles.signalThree}`}>
              <Store size={16} />
              <div>
                <strong>Open shop</strong>
                <span>Order in one tap</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.content}>
        {recent.length > 0 && !loading && (
          <div className={styles.recent}>
            <span>Recent</span>
            {recent.map((item) => (
              <button key={item} onClick={() => void ask(item)}>
                {item}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <section className={styles.loadingPanel}>
            <div className={styles.loadingCore}>
              <div className={styles.loadingRing} />
              <Bot size={24} />
            </div>
            <div>
              <span className={styles.sectionLabel}>RETAIL MIND AI</span>
              <h2>Comparing live shops…</h2>
              <p>Checking stock, prices, ratings and online availability.</p>
            </div>
            <div className={styles.loadingDots}>
              <span />
              <span />
              <span />
            </div>
          </section>
        )}

        {error && !loading && (
          <section className={styles.errorPanel} role="alert">
            <div className={styles.errorIcon}>
              <Bot size={21} />
            </div>
            <div className={styles.errorBody}>
              <span className={styles.sectionLabel}>SEARCH INTERRUPTED</span>
              <h2>Shopping AI needs another try.</h2>
              <p>{error}</p>
              <button
                className={styles.retryButton}
                onClick={() => void ask()}
                disabled={query.trim().length < 2}
              >
                Try again <ArrowRight size={15} />
              </button>
            </div>
          </section>
        )}

        {!loading && !error && available === false && (
          <section className={styles.emptyPanel}>
            <div className={styles.emptyOrb}>
              <Package size={30} />
              <span>0</span>
            </div>
            <div>
              <span className={styles.sectionLabel}>NO VERIFIED MATCH</span>
              <h2>Nothing available right now.</h2>
              <p>{message}</p>
              <div className={styles.emptyTips}>
                <span><CheckCircle2 size={14} /> Try a broader product name</span>
                <span><CheckCircle2 size={14} /> Relax the budget</span>
                <span><CheckCircle2 size={14} /> Try another shop</span>
              </div>
            </div>
          </section>
        )}

        {!loading && !error && available === true && (
          <>
            <section className={styles.answer}>
              <div className={styles.answerBadge}>
                <Bot size={18} />
              </div>
              <div className={styles.answerMain}>
                <div className={styles.answerMeta}>
                  <span className={styles.sectionLabel}>AI RECOMMENDATION</span>
                  {intent && <span className={styles.intent}>{intent}</span>}
                </div>
                <h2>{message}</h2>
                <div className={styles.answerTags}>
                  {productQuery && <span><Package size={13} /> {productQuery}</span>}
                  {shopHint && <span><Store size={13} /> {shopHint}</span>}
                </div>
              </div>
            </section>

            <div className={styles.resultsHeading}>
              <div>
                <span className={styles.sectionLabel}>VERIFIED OPTIONS</span>
                <h2>{results.length} real option{results.length === 1 ? '' : 's'}</h2>
              </div>
              <span className={styles.stockPill}>
                <span className={styles.liveDot} />
                Stock-aware
              </span>
            </div>

            <div className={styles.grid}>
              {results.map((item, index) => (
                <article
                  className={styles.result}
                  style={{ animationDelay: `${index * 70}ms` }}
                  key={String(item.product_id) + '-' + String(item.shop_id)}
                >
                  <div className={styles.resultGlow} />
                  <div className={styles.resultHeader}>
                    <div className={styles.productBadge}>
                      <Package size={19} />
                    </div>
                    <span className={styles.rank}>0{index + 1}</span>
                  </div>

                  <div className={styles.resultTitleRow}>
                    <h3>{item.product_name}</h3>
                    <div className={styles.price}>₹{Number(item.price).toFixed(2)}</div>
                  </div>

                  <p className={styles.resultDescription}>
                    {item.description || item.reason || 'Available for online ordering.'}
                  </p>

                  <div className={styles.shopRow}>
                    <div className={styles.shopBadge}>
                      <Store size={16} />
                    </div>
                    <div>
                      <strong>{item.shop_name}</strong>
                      <span>{item.shop_tagline || 'Online-enabled shop'}</span>
                    </div>
                  </div>

                  <div className={styles.metrics}>
                    <div>
                      <span>Rating</span>
                      <strong>
                        <Star size={13} fill="currentColor" />
                        {item.rating > 0 ? item.rating.toFixed(1) : 'New'}
                      </strong>
                    </div>
                    <div>
                      <span>Reviews</span>
                      <strong>{item.rating_count || 0}</strong>
                    </div>
                    <div>
                      <span>Stock</span>
                      <strong className={styles.goodStock}>
                        {Number(item.stock_available) > 0
                          ? String(item.stock_available) + ' left'
                          : 'Out'}
                      </strong>
                    </div>
                  </div>

                  {item.shop_address && (
                    <div className={styles.address}>
                      <MapPin size={13} />
                      {item.shop_address}
                    </div>
                  )}

                  {Number(item.online_setup_fee || 0) > 0 && (
                    <div className={styles.fee}>
                      Online setup fee ₹{Number(item.online_setup_fee).toFixed(2)} per order
                    </div>
                  )}

                  <div className={styles.actions}>
                    <Link
                      href={'/shop/' + item.shop_id + '/product/' + item.product_id}
                      className={styles.outlineButton}
                    >
                      Details
                    </Link>
                    <Link
                      href={'/shop/' + item.shop_id}
                      className={styles.fillButton}
                    >
                      Open shop
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  </div>
  );
}
