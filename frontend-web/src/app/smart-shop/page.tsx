'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Bot,
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
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { API_BASE } from '../../lib/api';

type BuyAgain = {
  product_id: number;
  shop_id: number;
  product_name?: string;
  last_price: number;
  last_quantity: number;
  order_id: number;
};

type Recommendation = {
  product_id: number;
  product_name: string;
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

function initials(name: string) {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((item) => item[0])
    .join('')
    .toUpperCase() || 'RM';
}

export default function SmartShopPage() {
  const router = useRouter();
  const [buyAgain, setBuyAgain] = useState<BuyAgain[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loyalty, setLoyalty] = useState<Loyalty | null>(null);
  const [returns, setReturns] = useState<ReturnRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  async function load() {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace('/auth');
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
        router.replace('/auth');
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

  const featuredProduct = recommendations[0];
  const buyAgainCount = buyAgain.length;
  const returnCount = returns.length;

  return (
    <main className="smart3d-page">
      <div className="smart3d-bg smart3d-bg-a" />
      <div className="smart3d-bg smart3d-bg-b" />
      <div className="smart3d-grid-floor" />

      <div className="container smart3d-shell">
        <section className="smart3d-hero">
          <div className="smart3d-hero-copy">
            <div className="smart3d-kicker">
              <span className="smart3d-kicker-dot" />
              RETAIL MIND / SMART HUB
            </div>

            <div className="smart3d-identity">
              <div className="smart3d-avatar">{initials(loyalty?.tier || 'Retail Mind')}</div>
              <div>
                <span>YOUR PERSONAL SHOPPING SPACE</span>
                <strong>Shop smarter. Stay ahead.</strong>
              </div>
            </div>

            <h1>
              Your shopping life,
              <span>beautifully connected.</span>
            </h1>

            <p className="smart3d-hero-lead">
              Reorder essentials, discover better-value products, collect rewards,
              and keep every return in one intelligent customer hub.
            </p>

            <div className="smart3d-hero-actions">
              <button className="smart3d-primary" onClick={() => router.push('/ai-shopping')}>
                <Sparkles size={16} /> Ask Retail Mind AI
                <ArrowRight size={15} />
              </button>
              <button className="smart3d-secondary" onClick={() => router.push('/orders')}>
                <ShoppingBag size={16} /> Open order centre
              </button>
            </div>

            <div className="smart3d-hero-proof">
              <span><ShieldCheck size={14} /> Secure account</span>
              <span><Clock3 size={14} /> Live order state</span>
              <span><WalletCards size={14} /> Reward-aware</span>
            </div>
          </div>

          <div className="smart3d-hero-visual" aria-hidden="true">
            <div className="smart3d-orbit smart3d-orbit-1" />
            <div className="smart3d-orbit smart3d-orbit-2" />
            <div className="smart3d-orbit smart3d-orbit-3" />

            <motion.div
              className="smart3d-core"
              animate={{
                y: [0, -12, 0],
                rotateX: [-3, 3, -3],
                rotateY: [5, -5, 5],
              }}
              transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}
            >
              <div className="smart3d-core-inner">
                <Bot size={42} />
                <span>SMART</span>
              </div>
            </motion.div>

            <motion.div
              className="smart3d-float smart3d-float-a"
              animate={{ y: [0, -9, 0], rotateZ: [-2, 1, -2] }}
              transition={{ duration: 5.5, repeat: Infinity, ease: 'easeInOut' }}
            >
              <Trophy size={15} />
              <div><strong>{loyalty?.points_balance ?? 0}</strong><span>points</span></div>
            </motion.div>

            <motion.div
              className="smart3d-float smart3d-float-b"
              animate={{ y: [0, 8, 0], rotateZ: [2, -1, 2] }}
              transition={{ duration: 5.8, repeat: Infinity, ease: 'easeInOut', delay: .4 }}
            >
              <Heart size={15} />
              <div><strong>{recommendations.length}</strong><span>smart picks</span></div>
            </motion.div>

            <motion.div
              className="smart3d-float smart3d-float-c"
              animate={{ y: [0, -6, 0], rotateZ: [1, -1, 1] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut', delay: .8 }}
            >
              <RotateCcw size={15} />
              <div><strong>{returnCount}</strong><span>returns</span></div>
            </motion.div>

            <div className="smart3d-caption">
              <span>PERSONAL COMMERCE ENGINE</span>
              <strong>BUY · REWARD · RETURN · REPEAT</strong>
            </div>
          </div>
        </section>

        {error && (
          <div className="smart3d-error">
            <RotateCcw size={16} />
            <div>
              <strong>We hit a temporary sync issue.</strong>
              <span>{error}</span>
            </div>
            <button onClick={() => void load()}>Retry</button>
          </div>
        )}

        <section className="smart3d-stats">
          <motion.article className="smart3d-stat smart3d-stat-gold" whileHover={{ y: -4 }}>
            <div className="smart3d-stat-icon"><Trophy size={18} /></div>
            <div><span>LOYALTY WALLET</span><strong>{loyalty?.points_balance ?? 0} pts</strong><p>{loyalty?.tier || 'Build your first tier'}</p></div>
            <Gift size={18} />
          </motion.article>

          <motion.article className="smart3d-stat smart3d-stat-green" whileHover={{ y: -4 }}>
            <div className="smart3d-stat-icon"><Heart size={18} /></div>
            <div><span>PERSONALIZED PICKS</span><strong>{recommendations.length} suggestions</strong><p>Chosen from your shopping patterns</p></div>
            <ChevronRight size={18} />
          </motion.article>

          <motion.article className="smart3d-stat smart3d-stat-blue" whileHover={{ y: -4 }}>
            <div className="smart3d-stat-icon"><RotateCcw size={18} /></div>
            <div><span>RETURNS</span><strong>{returnCount} open request{returnCount === 1 ? '' : 's'}</strong><p>{formatMoney(totalReturnValue)} pending value</p></div>
            <ArrowRight size={18} />
          </motion.article>
        </section>

        <section className="smart3d-section">
          <div className="smart3d-section-head">
            <div>
              <span>01 / BUY AGAIN</span>
              <h2>Essentials waiting for you.</h2>
              <p>One tap takes you straight back to the product.</p>
            </div>
            <button onClick={() => router.push('/orders')} className="smart3d-ghost-btn">
              View orders <ArrowRight size={14} />
            </button>
          </div>

          {loading ? (
            <div className="smart3d-skeleton-grid">
              {[1, 2, 3].map((item) => <div key={item} className="smart3d-skeleton-card" />)}
            </div>
          ) : buyAgain.length === 0 ? (
            <div className="smart3d-empty">
              <div className="smart3d-empty-icon"><Package size={20} /></div>
              <div>
                <strong>Your repeat shelf is empty.</strong>
                <span>Complete a few orders and your everyday essentials will appear here.</span>
              </div>
            </div>
          ) : (
            <div className="smart3d-product-grid">
              {buyAgain.slice(0, 6).map((item, index) => (
                <motion.button
                  key={item.product_id + '-' + item.shop_id}
                  className="smart3d-product-card"
                  onClick={() => router.push('/shop/' + item.shop_id + '/product/' + item.product_id)}
                  initial={{ opacity: 0, y: 16, rotateX: 8 }}
                  animate={{ opacity: 1, y: 0, rotateX: 0 }}
                  transition={{ duration: .4, delay: Math.min(index * .05, .2) }}
                  whileHover={{ y: -6, rotateY: -1.5 }}
                >
                  <div className="smart3d-product-art">
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <Package size={30} />
                  </div>
                  <div className="smart3d-product-copy">
                    <span>LAST PURCHASE</span>
                    <strong>{item.product_name || 'Product #' + item.product_id}</strong>
                    <small>Qty {item.last_quantity} · {formatMoney(item.last_price)}</small>
                  </div>
                  <div className="smart3d-product-action">
                    Buy again <ArrowRight size={14} />
                  </div>
                </motion.button>
              ))}
            </div>
          )}
        </section>

        <section className="smart3d-section smart3d-recommend-section">
          <div className="smart3d-section-head">
            <div>
              <span>02 / FOR YOU</span>
              <h2>Smart picks from live shops.</h2>
              <p>Real products, current pricing and reputation-aware suggestions.</p>
            </div>
            <div className="smart3d-live-pill"><i /> LIVE SHOP DATA</div>
          </div>

          {recommendations.length === 0 ? (
            <div className="smart3d-empty">
              <div className="smart3d-empty-icon"><Store size={20} /></div>
              <div>
                <strong>Your recommendation engine is warming up.</strong>
                <span>Start shopping and Retail Mind will learn what to surface next.</span>
              </div>
            </div>
          ) : (
            <div className="smart3d-recommend-grid">
              {recommendations.slice(0, 6).map((item, index) => (
                <motion.article
                  key={item.product_id + '-' + item.shop_id}
                  className="smart3d-rec-card"
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: .42, delay: Math.min(index * .05, .2) }}
                  whileHover={{ y: -6 }}
                >
                  <div className="smart3d-rec-top">
                    <div className="smart3d-rec-icon"><Store size={18} /></div>
                    <span className="smart3d-rec-number">0{index + 1}</span>
                  </div>
                  <div className="smart3d-rec-kicker">{item.category || 'SMART MATCH'}</div>
                  <h3>{item.product_name}</h3>
                  <p>{item.shop_name}</p>

                  <div className="smart3d-rec-meta">
                    <span><Star size={12} fill="currentColor" /> {item.rating > 0 ? item.rating.toFixed(1) : 'New'}</span>
                    <span>{item.rating_count || 0} reviews</span>
                    <span>{item.stock_available > 0 ? item.stock_available + ' in stock' : 'Out of stock'}</span>
                  </div>

                  <div className="smart3d-rec-bottom">
                    <strong>{formatMoney(item.price)}</strong>
                    <button onClick={() => router.push('/shop/' + item.shop_id + '/product/' + item.product_id)}>
                      Explore <ArrowRight size={13} />
                    </button>
                  </div>
                </motion.article>
              ))}
            </div>
          )}
        </section>

        <section className="smart3d-return-section">
          <div className="smart3d-return-visual">
            <div className="smart3d-return-ring" />
            <RotateCcw size={28} />
          </div>
          <div className="smart3d-return-copy">
            <span>03 / RETURNS & REFUNDS</span>
            <h2>Everything stays visible.</h2>
            <p>
              Track every return request, refund state and pending amount without hunting
              through your order history.
            </p>

            {returns.length === 0 ? (
              <div className="smart3d-return-empty">No return requests yet.</div>
            ) : (
              <div className="smart3d-return-list">
                {returns.slice(0, 4).map((row) => (
                  <div key={row.id} className="smart3d-return-row">
                    <div>
                      <strong>Order #{row.order_id}</strong>
                      <span>{row.reason}</span>
                    </div>
                    <div className="smart3d-return-right">
                      <b>{row.status.replaceAll('_', ' ')}</b>
                      <span>{formatMoney(row.refund_amount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <button className="smart3d-light-btn" onClick={() => router.push('/orders')}>
              Manage returns in Order Centre <ArrowRight size={14} />
            </button>
          </div>
        </section>

        <section className="smart3d-bottom-cta">
          <div>
            <span>READY FOR YOUR NEXT MOVE?</span>
            <h2>Let Retail Mind shop with you.</h2>
          </div>
          <button onClick={() => router.push('/ai-shopping')}>
            <Sparkles size={16} /> Find my next best buy
          </button>
        </section>
      </div>
    </main>
  );
}
