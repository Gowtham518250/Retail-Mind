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
import { motion, useReducedMotion } from 'framer-motion';
import ProductImage from '../../components/ProductImage';
import styles from './page.module.css';

type Recommendation = {
  product_id: number;
  product_name: string;
  image_url?: string;
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
  const shouldReduceMotion = Boolean(useReducedMotion());
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
    <main className={styles.page} data-experience="ai-shopping">
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
              RETAIL MIND / PERSONAL SHOPPING COPILOT
            </div>

            <div className={styles.eyebrowLine}>
              <span>LIVE PRODUCTS</span>
              <i />
              <span>LIVE RATINGS</span>
              <i />
              <span>LOCAL CHECKOUT</span>
            </div>

            <h1>
              Think it.
              <span>Say it.</span>
              <em>Shop it.</em>
            </h1>

            <p className={styles.heroLead}>
              Tell us what you need, from a product and budget to a preferred
              shop or rating. Retail Mind turns your words into a live shortlist
              from neighbourhood stores.
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
                    Find matches
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
            <div className={styles.showroomStage}>
              <div className={styles.showroomGlow} />
              <div className={styles.showroomRing + ' ' + styles.showroomRingA} />
              <div className={styles.showroomRing + ' ' + styles.showroomRingB} />
              
              {/* Central AI Commerce Core */}
              <motion.div
                className={styles.aiCore}
                animate={shouldReduceMotion ? { y: 0 } : { y: [0, -6, 0] }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 6, repeat: Infinity, ease: 'easeInOut' }}
              >
                <div className={styles.aiCoreHeader}>
                  <Sparkles size={14} className={styles.sparkleIcon} />
                  <span>RETAIL INTELLIGENCE</span>
                  <div className={styles.pulseDot} />
                </div>
                <div className={styles.aiCoreBody}>
                  <div className={styles.aiCoreAvatar}>
                    <Bot size={30} />
                  </div>
                    <strong>Local shopping copilot</strong>
                    <p>Comparing live stock, prices and ratings near you</p>
                </div>
              </motion.div>

              {/* Floating Product Chips */}
              <motion.div
                className={styles.floatingChip + ' ' + styles.chipA}
                animate={shouldReduceMotion ? { y: 0 } : { y: [0, -8, 0] }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 5.4, repeat: Infinity, ease: 'easeInOut', delay: 0.2 }}
              >
                <div className={styles.chipIcon}><ShoppingBag size={14} /></div>
                <div>
                  <strong>Aashirvaad Atta</strong>
                  <span>₹420 · In stock</span>
                </div>
                <span className={styles.chipTag}>Best Price</span>
              </motion.div>

              <motion.div
                className={styles.floatingChip + ' ' + styles.chipB}
                animate={shouldReduceMotion ? { y: 0 } : { y: [0, 8, 0] }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 5.8, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
              >
                <div className={styles.chipIcon}><Star size={14} fill="currentColor" /></div>
                <div>
                  <strong>Amul Butter</strong>
                  <span>₹56 · 4.9 ★</span>
                </div>
                <span className={styles.chipTag}>Top Rated</span>
              </motion.div>

              <motion.div
                className={styles.floatingChip + ' ' + styles.chipC}
                animate={shouldReduceMotion ? { y: 0 } : { y: [0, -6, 0] }}
                transition={shouldReduceMotion ? { duration: 0 } : { duration: 6.2, repeat: Infinity, ease: 'easeInOut', delay: 0.8 }}
              >
                <div className={styles.chipIcon}><Zap size={14} /></div>
                <div>
                  <strong>Tata Tea Gold</strong>
                  <span>₹190 · Near you</span>
                </div>
                <span className={styles.chipTag}>Verified</span>
              </motion.div>

              <div className={styles.showroomStatsBar}>
                <div className={styles.statPill}><Store size={13} /> <strong>100%</strong> local inventory</div>
                <div className={styles.statPill}><Star size={13} /> <strong>4.8+</strong> verified ratings</div>
                <div className={styles.statPill}><ShieldCheck size={13} /> <strong>Instant</strong> checkout</div>
              </div>
            </div>
          </div>        </div>
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
                  <span className={styles.sectionLabel}>SMART MATCHES</span>
                  <h2>Best options for your basket</h2>
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
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={
                    shouldReduceMotion
                      ? { duration: 0 }
                      : {
                          duration: 0.35,
                          delay: Math.min(index * 0.04, 0.24),
                          ease: [0.22, 1, 0.36, 1],
                        }
                  }
                >
                  <div className={styles.resultImageFrame}>
                    <ProductImage
                      src={item.image_url}
                      productName={item.product_name}
                      alt={item.product_name}
                      width={300}
                      height={190}
                      sizes="(max-width: 768px) 100vw, 360px"
                      className={styles.productCardImg}
                    />
                    <div className={styles.resultHeaderOverlay}>
                      <span className={styles.rankPill}>
                        <Sparkles size={11} /> MATCH #{index + 1}
                      </span>
                      {Number(item.rating || 0) >= 4.5 && (
                        <span className={styles.topChoicePill}>
                          <Star size={11} fill="currentColor" /> Top Rated
                        </span>
                      )}
                    </div>
                  </div>

                  <div className={styles.resultCardContent}>
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
                        <Store size={15} />
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
                            ? String(item.stock_available) + ' in stock'
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
