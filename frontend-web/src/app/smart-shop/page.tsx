'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Gift,
  Heart,
  Package,
  RotateCcw,
  Sparkles,
  Star,
  Store,
  Trophy,
  WalletCards,
  Clock3,
  ShoppingBag,
  ShieldCheck,
  ChevronRight,
  TrendingUp,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { API_BASE } from '../../lib/api';
import ProductImage from '../../components/ProductImage';
import styles from './smart-shop.module.css';

type BuyAgain = {
  product_id: number;
  shop_id: number;
  product_name?: string;
  image_url?: string | null;
  category?: string;
  last_price: number;
  last_quantity: number;
  order_id: number;
};

type Recommendation = {
  product_id: number;
  product_name: string;
  image_url?: string | null;
  price: number;
  stock_available: number;
  category?: string;
  shop_id: number;
  shop_name: string;
  rating: number;
  rating_count: number;
};

type Loyalty = {
  shop_id: number;
  points_balance: number;
  lifetime_earned: number;
  lifetime_redeemed: number;
  tier: string;
  rupee_value: number;
};

type ReturnRow = {
  id: number;
  order_id: number;
  reason: string;
  status: string;
  refund_amount: number;
};

function formatMoney(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

export default function SmartShopPage() {
  const router = useRouter();
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [buyAgain, setBuyAgain] = useState<BuyAgain[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loyalty, setLoyalty] = useState<Loyalty | null>(null);
  const [returns, setReturns] = useState<ReturnRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace('/auth?next=%2Fsmart-shop');
      return;
    }

    try {
      setLoading(true);
      setError('');

      const headers = { Authorization: 'Bearer ' + token };
      const [buyRes, recRes, returnRes] = await Promise.all([
        fetch(API_BASE + '/store/buy-again', { headers, cache: 'no-store' }),
        fetch(API_BASE + '/store/recommendations', { headers, cache: 'no-store' }),
        fetch(API_BASE + '/store/returns', { headers, cache: 'no-store' }),
      ]);

      if ([buyRes, recRes, returnRes].some((res) => res.status === 401 || res.status === 403)) {
        localStorage.removeItem('customerToken');
        router.replace('/auth?next=%2Fsmart-shop');
        return;
      }

      const [buy, rec, ret] = await Promise.all([
        buyRes.json(),
        recRes.json(),
        returnRes.json(),
      ]);

      const nextBuyAgain = Array.isArray(buy.items) ? buy.items : [];
      const nextRecommendations = Array.isArray(rec.recommendations) ? rec.recommendations : [];
      const nextReturns = Array.isArray(ret.returns) ? ret.returns : [];

      setBuyAgain(nextBuyAgain);
      setRecommendations(nextRecommendations);
      setReturns(nextReturns);

      const shopId = Number(
        nextBuyAgain[0]?.shop_id ||
        nextRecommendations[0]?.shop_id ||
        0,
      );

      if (shopId > 0) {
        const loyaltyResponse = await fetch(
          API_BASE + '/store/loyalty?shop_id=' + shopId,
          { headers, cache: 'no-store' },
        );
        if (loyaltyResponse.ok) {
          setLoyalty(await loyaltyResponse.json());
        }
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to load your Smart Hub right now.',
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const totalReturnValue = useMemo(
    () => returns.reduce((sum, row) => sum + Number(row.refund_amount || 0), 0),
    [returns],
  );

  const returnCount = returns.length;

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        {/* ───────── Hero Banner ───────── */}
        <section className={styles.hero}>
          <div className={styles.heroCopy}>
            <div className={styles.kicker}>
              <span className={styles.kickerDot} />
              RETAIL MIND · SMART COMMERCE HUB
            </div>

            <h1>
              Your shopping life,
              <span className={styles.heroAccent}>beautifully connected.</span>
            </h1>

            <p className={styles.heroLead}>
              One-tap reorders, AI-matched value recommendations, loyalty savings,
              and live return tracking all in one unified place.
            </p>

            <div className={styles.heroActions}>
              <button
                type="button"
                className={styles.primaryBtn}
                onClick={() => router.push('/ai-shopping')}
              >
                <Sparkles size={16} /> Ask AI Assistant
                <ArrowRight size={15} />
              </button>
              <button
                type="button"
                className={styles.secondaryBtn}
                onClick={() => router.push('/orders')}
              >
                <ShoppingBag size={16} /> View Orders & Hub
              </button>
            </div>

            <div className={styles.heroProof}>
              <span><ShieldCheck size={14} /> Verified local shops</span>
              <span><Clock3 size={14} /> Live order dispatch</span>
              <span><WalletCards size={14} /> Reward points enabled</span>
            </div>
          </div>

          <div className={styles.heroHubBoard} aria-label="Customer commerce summary">
            <div className={styles.hubBoardTitle}>
              <span>Customer Snapshot</span>
              <TrendingUp size={15} />
            </div>

            <div className={styles.hubBoardRow}>
              <div className={styles.hubBoardRowItem}>
                <div className={styles.hubBoardIcon}>
                  <Trophy size={18} />
                </div>
                <div className={styles.hubBoardCopy}>
                  <strong>{loyalty?.points_balance ?? 0} Points</strong>
                  <small>{loyalty?.tier || 'Silver Member'}</small>
                </div>
              </div>
              <ChevronRight size={16} color="rgba(255,255,255,0.4)" />
            </div>

            <div className={styles.hubBoardRow}>
              <div className={styles.hubBoardRowItem}>
                <div className={`${styles.hubBoardIcon} ${styles.hubBoardIconGreen}`}>
                  <Heart size={18} />
                </div>
                <div className={styles.hubBoardCopy}>
                  <strong>{recommendations.length} Recommended</strong>
                  <small>Personalized for you</small>
                </div>
              </div>
              <ChevronRight size={16} color="rgba(255,255,255,0.4)" />
            </div>

            <div className={styles.hubBoardRow}>
              <div className={styles.hubBoardRowItem}>
                <div className={`${styles.hubBoardIcon} ${styles.hubBoardIconBlue}`}>
                  <RotateCcw size={18} />
                </div>
                <div className={styles.hubBoardCopy}>
                  <strong>{returnCount} Return{returnCount === 1 ? '' : 's'}</strong>
                  <small>{formatMoney(totalReturnValue)} pending value</small>
                </div>
              </div>
              <ChevronRight size={16} color="rgba(255,255,255,0.4)" />
            </div>
          </div>
        </section>

        {error && (
          <div className={styles.errorBanner} role="alert" style={{ marginTop: 20, padding: 16, background: '#fee2e2', borderRadius: 16, display: 'flex', alignItems: 'center', gap: 12, color: '#991b1b' }}>
            <AlertCircle size={18} />
            <div style={{ flex: 1 }}>
              <strong>We hit a temporary sync issue.</strong>
              <div style={{ fontSize: 13 }}>{error}</div>
            </div>
            <button
              type="button"
              onClick={() => void load()}
              style={{ padding: '6px 14px', borderRadius: 8, background: '#991b1b', color: '#fff', border: 0, cursor: 'pointer', fontWeight: 700 }}
            >
              Retry
            </button>
          </div>
        )}

        {/* ───────── Stats Strip ───────── */}
        <section className={styles.statsGrid}>
          <motion.article
            className={styles.statCard}
            whileHover={shouldReduceMotion ? undefined : { y: -2 }}
          >
            <div className={styles.statIconWrap}>
              <Trophy size={22} />
            </div>
            <div className={styles.statCopy}>
              <span className={styles.statLabel}>Loyalty Wallet</span>
              <strong className={styles.statValue}>{loyalty?.points_balance ?? 0} pts</strong>
              <span className={styles.statDesc}>{loyalty?.tier || 'Member Tier'} · Redeemable at checkout</span>
            </div>
          </motion.article>

          <motion.article
            className={styles.statCard}
            whileHover={shouldReduceMotion ? undefined : { y: -2 }}
          >
            <div className={`${styles.statIconWrap} ${styles.statIconGreen}`}>
              <Heart size={22} />
            </div>
            <div className={styles.statCopy}>
              <span className={styles.statLabel}>Curated Suggestions</span>
              <strong className={styles.statValue}>{recommendations.length} Picks</strong>
              <span className={styles.statDesc}>Matched to your taste and local shops</span>
            </div>
          </motion.article>

          <motion.article
            className={styles.statCard}
            whileHover={shouldReduceMotion ? undefined : { y: -2 }}
          >
            <div className={`${styles.statIconWrap} ${styles.statIconBlue}`}>
              <RotateCcw size={22} />
            </div>
            <div className={styles.statCopy}>
              <span className={styles.statLabel}>Returns & Refunds</span>
              <strong className={styles.statValue}>{returnCount} Open</strong>
              <span className={styles.statDesc}>{formatMoney(totalReturnValue)} tracked refund value</span>
            </div>
          </motion.article>
        </section>

        {/* ───────── Section 01: Buy Again / Essentials Waiting for You ───────── */}
        <section className={styles.section}>
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.sectionTag}>01 / Buy Again</span>
              <h2>Essentials waiting for you.</h2>
              <p>One tap takes you straight back to reorder everyday products.</p>
            </div>
            <button
              type="button"
              onClick={() => router.push('/orders')}
              className={styles.ghostBtn}
            >
              View orders <ArrowRight size={14} />
            </button>
          </div>

          {loading ? (
            <div className={styles.skeletonGrid}>
              {[1, 2, 3].map((item) => (
                <div key={item} className={styles.skeletonCard} />
              ))}
            </div>
          ) : buyAgain.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}><Package size={24} /></div>
              <strong>Your repeat shelf is empty.</strong>
              <span>Complete an order and your everyday essentials will appear here for fast 1-tap reordering.</span>
            </div>
          ) : (
            <div className={styles.productGrid}>
              {buyAgain.slice(0, 6).map((item, index) => (
                <motion.article
                  key={`${item.product_id}-${item.shop_id}`}
                  className={styles.productCard}
                  onClick={() => router.push(`/shop/${item.shop_id}/product/${item.product_id}`)}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.35, delay: Math.min(index * 0.05, 0.2) }}
                  whileHover={shouldReduceMotion ? undefined : { y: -4 }}
                >
                  <div className={styles.productMedia}>
                    <ProductImage
                      src={item.image_url}
                      name={item.product_name}
                      category={item.category}
                      className={styles.productThumb}
                      alt={item.product_name || 'Product'}
                    />
                    <span className={styles.orderBadge}>
                      Ordered {item.last_quantity}x
                    </span>
                    <span className={styles.indexPill}>
                      {String(index + 1).padStart(2, '0')}
                    </span>
                  </div>

                  <div className={styles.productBody}>
                    <span className={styles.productKicker}>Previous Purchase</span>
                    <h3 className={styles.productTitle}>
                      {item.product_name || `Product #${item.product_id}`}
                    </h3>

                    <div className={styles.productMeta}>
                      <span className={styles.productMetaQty}>
                        Last Qty: {item.last_quantity}
                      </span>
                      <strong className={styles.productPrice}>
                        {formatMoney(item.last_price)}
                      </strong>
                    </div>

                    <button
                      type="button"
                      className={styles.buyAgainBtn}
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(`/shop/${item.shop_id}/product/${item.product_id}`);
                      }}
                    >
                      <ShoppingBag size={14} /> Buy again <ArrowRight size={13} />
                    </button>
                  </div>
                </motion.article>
              ))}
            </div>
          )}
        </section>

        {/* ───────── Section 02: Smart Picks / Recommendations ───────── */}
        <section className={`${styles.section} ${styles.recommendSection}`}>
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.sectionTag}>02 / For You</span>
              <h2>Smart picks from live shops.</h2>
              <p>Real products, current local shelf pricing, and reputation-aware suggestions.</p>
            </div>
            <div className={styles.livePill}>
              <i /> LIVE SHOP DATA
            </div>
          </div>

          {recommendations.length === 0 ? (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}><Store size={24} /></div>
              <strong>Your recommendation engine is warming up.</strong>
              <span>Start shopping neighbourhood shelves and Retail Mind will surface personalized local picks.</span>
            </div>
          ) : (
            <div className={styles.recGrid}>
              {recommendations.slice(0, 6).map((item, index) => (
                <motion.article
                  key={`${item.product_id}-${item.shop_id}`}
                  className={styles.recCard}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.35, delay: Math.min(index * 0.05, 0.2) }}
                  whileHover={shouldReduceMotion ? undefined : { y: -4 }}
                >
                  <div className={styles.recMedia}>
                    <ProductImage
                      src={item.image_url}
                      name={item.product_name}
                      category={item.category}
                      className={styles.productThumb}
                      alt={item.product_name}
                    />
                    <div className={styles.recRatingBadge}>
                      <Star size={11} fill="currentColor" />
                      <span>{item.rating > 0 ? item.rating.toFixed(1) : 'New'}</span>
                    </div>
                  </div>

                  <div className={styles.recBody}>
                    <span className={styles.recCategory}>{item.category || 'Featured Pick'}</span>
                    <h3 className={styles.recTitle}>{item.product_name}</h3>
                    <div className={styles.recShop}>
                      <Store size={13} /> {item.shop_name}
                    </div>

                    <div className={`${styles.recStockBadge} ${item.stock_available <= 0 ? styles.outOfStock : ''}`}>
                      {item.stock_available > 0 ? (
                        <>
                          <CheckCircle2 size={12} /> {item.stock_available} available in store
                        </>
                      ) : (
                        <>
                          <AlertCircle size={12} /> Out of stock
                        </>
                      )}
                    </div>

                    <div className={styles.recFooter}>
                      <strong className={styles.recPrice}>{formatMoney(item.price)}</strong>
                      <button
                        type="button"
                        className={styles.recActionBtn}
                        onClick={() => router.push(`/shop/${item.shop_id}/product/${item.product_id}`)}
                      >
                        Explore <ArrowRight size={13} />
                      </button>
                    </div>
                  </div>
                </motion.article>
              ))}
            </div>
          )}
        </section>

        {/* ───────── Section 03: Returns & Refunds ───────── */}
        <section className={styles.returnSection}>
          <div className={styles.returnVisual}>
            <div className={styles.returnVisualIcon}>
              <RotateCcw size={28} />
            </div>
            <strong>{formatMoney(totalReturnValue)}</strong>
            <span>Total Tracked Returns</span>
          </div>

          <div className={styles.returnCopy}>
            <span className={styles.returnCopyTag}>03 / Returns & Refunds</span>
            <h2>Everything stays completely visible.</h2>
            <p>
              Track every return request, pickup window, refund status, and settlement amount
              directly without digging through past order slips.
            </p>

            {returns.length === 0 ? (
              <div style={{ padding: '12px 16px', background: 'rgba(255,255,255,0.06)', borderRadius: 12, color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>
                No active return requests. All your delivered orders are in good standing!
              </div>
            ) : (
              <div className={styles.returnList}>
                {returns.slice(0, 3).map((row) => (
                  <div key={row.id} className={styles.returnRow}>
                    <div className={styles.returnRowInfo}>
                      <strong>Order #{row.order_id}</strong>
                      <span>{row.reason}</span>
                    </div>
                    <div className={styles.returnRowRight}>
                      <span className={styles.returnStatusPill}>
                        {row.status.replaceAll('_', ' ')}
                      </span>
                      <strong className={styles.returnAmount}>
                        {formatMoney(row.refund_amount)}
                      </strong>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button
              type="button"
              className={styles.returnLightBtn}
              onClick={() => router.push('/orders')}
            >
              Manage in Order Centre <ArrowRight size={14} />
            </button>
          </div>
        </section>

        {/* ───────── Bottom CTA ───────── */}
        <section className={styles.bottomCta}>
          <div className={styles.bottomCtaCopy}>
            <span>Intelligent Neighbourhood Commerce</span>
            <h2>Let Retail Mind discover the best prices near you.</h2>
          </div>
          <button
            type="button"
            className={styles.bottomCtaBtn}
            onClick={() => router.push('/ai-shopping')}
          >
            <Sparkles size={16} /> Open AI Shopping Assistant
          </button>
        </section>
      </div>
    </main>
  );
}
