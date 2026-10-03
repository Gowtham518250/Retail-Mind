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
  BrainCircuit,
  ScanSearch,
  SlidersHorizontal,
} from 'lucide-react';
import Link from 'next/link';
import { motion } from 'framer-motion';
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
  'best rated shampoo under ₹500',
];

function metric(value: number, suffix = '') {
  return String(value).replace(/\.0$/, '') + suffix;
}

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
        '/api/ai-shopping?q=' + encodeURIComponent(value) + '&limit=10',
        { cache: 'no-store' },
      );
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(
          typeof data?.detail === 'string'
            ? data.detail
            : 'The shopping assistant could not complete that search.',
        );
      }

      const recommendations = Array.isArray(data.recommendations)
        ? data.recommendations
        : [];

      setAvailable(recommendations.length > 0);
      setMessage(
        data.response ||
          data.message ||
          (recommendations.length
            ? 'I found matching products from online-enabled shops.'
            : 'I could not find a verified match right now.'),
      );
      setIntent(
        data.intent?.rating_priority
          ? 'Rating-aware'
          : data.intent?.low_price
            ? 'Price-aware'
            : 'Smart match',
      );
      setProductQuery(data.query || value);
      setShopHint('');
      setResults(recommendations);
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
      <div className={styles.noise} />
      <div className={styles.gridFloor} />
      <div className={styles.ambient + ' ' + styles.ambientOne} />
      <div className={styles.ambient + ' ' + styles.ambientTwo} />
      <div className={styles.ambient + ' ' + styles.ambientThree} />

      <section className={styles.hero}>
        <div className={styles.navRow}>
          <Link href="/" className={styles.backLink}>
            <ChevronLeft size={15} />
            Marketplace
          </Link>

          <div className={styles.liveBadge}>
            <span className={styles.liveDot} />
            LIVE RETAIL INTELLIGENCE
          </div>
        </div>

        <div className={styles.heroInner}>
          <div className={styles.copy}>
            <div className={styles.kicker}>
              <BrainCircuit size={14} />
              RETAIL MIND / AI SHOPPING ENGINE
            </div>

            <div className={styles.eyebrowLine}>
              <span>REAL INVENTORY</span>
              <i />
              <span>LIVE RATINGS</span>
              <i />
              <span>SHOP-READY</span>
            </div>

            <h1>
              Think it.
              <span>Say it.</span>
              <em>Shop it.</em>
            </h1>

            <p className={styles.heroLead}>
              Describe the outcome you want — product, budget, shop or rating.
              Retail Mind turns that sentence into a live shortlist from
              online-enabled neighbourhood stores.
            </p>

            <div className={styles.commandBar}>
              <div className={styles.commandPrefix}>
                <ScanSearch size={18} />
              </div>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void ask();
                }}
                placeholder="Ask: “best rated shampoo under ₹500”"
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
                    Thinking
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
              <span>TRY</span>
              {examples.map((example) => (
                <button key={example} onClick={() => void ask(example)}>
                  {example}
                </button>
              ))}
            </div>

            <div className={styles.trustRow}>
              <span><ShieldCheck size={14} /> Verified inventory</span>
              <span><Star size={14} /> Reputation-aware</span>
              <span><ShoppingBag size={14} /> Local checkout</span>
            </div>
          </div>

          <div className={styles.visual} aria-hidden="true">
            <div className={styles.holoStage}>
              <div className={styles.holoFloor} />
              <div className={`${styles.orbit} ${styles.orbitOne}`} />
              <div className={`${styles.orbit} ${styles.orbitTwo}`} />
              <div className={`${styles.orbit} ${styles.orbitThree}`} />

              <motion.div
                className={styles.aiCore}
                animate={{
                  y: [0, -12, 0],
                  rotateX: [-4, 4, -4],
                  rotateY: [6, -6, 6],
                }}
                transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
              >
                <div className={styles.aiCoreShell}>
                  <div className={styles.aiCoreGlass} />
                  <Bot size={44} />
                  <span className={styles.corePulse} />
                </div>
              </motion.div>

              <motion.div
                className={styles.dataCard + ' ' + styles.dataCardA}
                animate={{ y: [0, -9, 0], rotateZ: [-2, 1, -2] }}
                transition={{ duration: 5.2, repeat: Infinity, ease: 'easeInOut' }}
              >
                <Package size={16} />
                <div>
                  <strong>12 shops</strong>
                  <span>inventory scanned</span>
                </div>
              </motion.div>

              <motion.div
                className={styles.dataCard + ' ' + styles.dataCardB}
                animate={{ y: [0, 8, 0], rotateZ: [2, -1, 2] }}
                transition={{ duration: 5.8, repeat: Infinity, ease: 'easeInOut', delay: .6 }}
              >
                <Star size={16} />
                <div>
                  <strong>4.8 avg</strong>
                  <span>shop rating signal</span>
                </div>
              </motion.div>

              <motion.div
                className={styles.dataCard + ' ' + styles.dataCardC}
                animate={{ y: [0, -6, 0], rotateZ: [1, -1, 1] }}
                transition={{ duration: 4.8, repeat: Infinity, ease: 'easeInOut', delay: .9 }}
              >
                <Sparkles size={16} />
                <div>
                  <strong>Value match</strong>
                  <span>AI ranking layer</span>
                </div>
              </motion.div>

              <div className={styles.sceneCaption}>
                <span>AI SEARCH CORE</span>
                <strong>LOCAL COMMERCE / ONLINE</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.content}>
        {recent.length > 0 && !loading && (
          <div className={styles.recent}>
            <span>RECENT COMMANDS</span>
            {recent.map((item) => (
              <button key={item} onClick={() => void ask(item)}>
                {item}
              </button>
            ))}
          </div>
        )}

        {loading && (
          <section className={styles.responseStage}>
            <div className={styles.responseGlow} />
            <div className={styles.responseIcon}>
              <div className={styles.responseIconRing} />
              <Bot size={24} />
            </div>
            <div className={styles.responseCopy}>
              <span className={styles.sectionLabel}>RETAIL MIND AI</span>
              <h2>Building your shopping answer…</h2>
              <p>Cross-checking live stock, price, ratings and shop availability.</p>
              <div className={styles.thinkingSteps}>
                <span><i /> Inventory scan</span>
                <span><i /> Value ranking</span>
                <span><i /> Shop matching</span>
              </div>
            </div>
          </section>
        )}

        {error && !loading && (
          <section className={styles.responseStage + ' ' + styles.errorStage}>
            <div className={styles.responseIcon}>
              <Bot size={24} />
            </div>
            <div className={styles.responseCopy}>
              <span className={styles.sectionLabel}>SEARCH INTERRUPTED</span>
              <h2>The AI needs another pass.</h2>
              <p>{error}</p>
              <button className={styles.retryButton} onClick={() => void ask()}>
                Try again <ArrowRight size={15} />
              </button>
            </div>
          </section>
        )}

        {!loading && !error && available === null && (
          <section className={styles.introGrid}>
            <div className={styles.introCard + ' ' + styles.introMain}>
              <div className={styles.introOrb}>
                <Bot size={28} />
              </div>
              <div>
                <span className={styles.sectionLabel}>READY WHEN YOU ARE</span>
                <h2>Give Retail Mind a normal sentence.</h2>
                <p>
                  “Find me the best-rated ghee under ₹350 near my neighbourhood”
                  is enough. The engine translates intent into actual store data.
                </p>
              </div>
            </div>
            <div className={styles.introCard}>
              <div className={styles.miniIcon}><SlidersHorizontal size={18} /></div>
              <strong>More context = better matching</strong>
              <span>Add budget, preferred shop, category or “best rated”.</span>
            </div>
            <div className={styles.introCard}>
              <div className={styles.miniIcon}><Store size={18} /></div>
              <strong>Local stores stay local</strong>
              <span>Only online-enabled shops are surfaced for checkout.</span>
            </div>
          </section>
        )}

        {!loading && !error && available === false && (
          <section className={styles.responseStage + ' ' + styles.emptyStage}>
            <div className={styles.responseIcon}>
              <Package size={24} />
            </div>
            <div className={styles.responseCopy}>
              <span className={styles.sectionLabel}>NO VERIFIED MATCH</span>
              <h2>Nothing matched this command yet.</h2>
              <p>{message}</p>
              <div className={styles.thinkingSteps}>
                <span><CheckCircle2 size={13} /> Broaden the product name</span>
                <span><CheckCircle2 size={13} /> Relax the budget</span>
                <span><CheckCircle2 size={13} /> Try another shop</span>
              </div>
            </div>
          </section>
        )}

        {!loading && !error && available === true && (
          <>
            <section className={styles.answerDeck}>
              <div className={styles.answerBack} />
              <div className={styles.answerMain}>
                <div className={styles.answerHead}>
                  <div className={styles.answerBot}>
                    <Bot size={20} />
                  </div>
                  <div>
                    <span className={styles.sectionLabel}>AI RESPONSE</span>
                    <div className={styles.answerIntent}>{intent}</div>
                  </div>
                  <span className={styles.livePill}>
                    <span className={styles.liveDot} />
                    LIVE DATA
                  </span>
                </div>
                <h2>{message}</h2>
                <div className={styles.answerChips}>
                  {productQuery && <span><Package size={13} /> {productQuery}</span>}
                  {shopHint && <span><Store size={13} /> {shopHint}</span>}
                  <span><CheckCircle2 size={13} /> Verified options only</span>
                </div>
              </div>
              <div className={styles.answerSide}>
                <div>
                  <span>OPTIONS</span>
                  <strong>{results.length}</strong>
                </div>
                <div>
                  <span>BEST RATING</span>
                  <strong>{results.length ? metric(Math.max(...results.map((r) => Number(r.rating || 0))), '/5') : '—'}</strong>
                </div>
              </div>
            </section>

            <div className={styles.resultsHeading}>
              <div>
                <span className={styles.sectionLabel}>3D VALUE BOARD</span>
                <h2>Options the AI wants you to see</h2>
              </div>
              <span className={styles.stockPill}>
                <span className={styles.liveDot} />
                Stock-aware
              </span>
            </div>

            <div className={styles.grid}>
              {results.map((item, index) => (
                <motion.article
                  className={styles.result}
                  key={String(item.product_id) + '-' + String(item.shop_id)}
                  initial={{ opacity: 0, y: 24, rotateX: 9 }}
                  animate={{ opacity: 1, y: 0, rotateX: 0 }}
                  transition={{
                    duration: .5,
                    delay: Math.min(index * .07, .35),
                    ease: [.22, .7, .25, 1],
                  }}
                >
                  <div className={styles.resultDepth} />
                  <div className={styles.resultHeader}>
                    <div className={styles.productBadge}>
                      <Package size={18} />
                    </div>
                    <span className={styles.rank}>0{index + 1}</span>
                  </div>

                  <div className={styles.resultTitleRow}>
                    <div>
                      <span className={styles.resultKicker}>MATCH {String(index + 1).padStart(2, '0')}</span>
                      <h3>{item.product_name}</h3>
                    </div>
                    <div className={styles.price}>
                      ₹{Number(item.price).toFixed(2)}
                    </div>
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
                      Open shop <ArrowRight size={14} />
                    </Link>
                  </div>
                </motion.article>
              ))}
            </div>
          </>
        )}
      </section>
    </main>
  );
}
