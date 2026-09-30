'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Clock3,
  MapPin,
  Package,
  RefreshCw,
  Truck,
  XCircle,
  Sparkles,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';
import { useLanguage } from '../../context/LanguageContext';

interface OrderItem {
  product_id: number;
  product_name?: string;
  quantity: number;
  unit_price?: number;
  line_total?: number;
}

interface Order {
  order_id: number;
  shop_id: number;
  shop_name?: string;
  status: string;
  total_amount: number;
  delivery_address: string;
  items: OrderItem[];
  created_at: string;
}

const STEPS = ['PENDING', 'ACCEPTED', 'DISPATCHED', 'DELIVERED'] as const;

const statusMeta: Record<string, {
  title: string;
  description: string;
  icon: typeof Clock3;
  tone: string;
}> = {
  PENDING: {
    title: 'Order placed',
    description: 'Your order is waiting for the shop to confirm it.',
    icon: Clock3,
    tone: '#f59e0b',
  },
  ACCEPTED: {
    title: 'Order accepted',
    description: 'The shop has accepted your order and will prepare it.',
    icon: CheckCircle2,
    tone: '#22d3ee',
  },
  DISPATCHED: {
    title: 'Out for delivery',
    description: 'Your order has been dispatched from the shop.',
    icon: Truck,
    tone: '#818cf8',
  },
  DELIVERED: {
    title: 'Delivered',
    description: 'Your order has been marked as delivered.',
    icon: Check,
    tone: '#10b981',
  },
  REJECTED: {
    title: 'Order rejected',
    description: 'The shop could not fulfil this order.',
    icon: XCircle,
    tone: '#f87171',
  },
};

function normalizeOrder(raw: any): Order {
  return {
    order_id: Number(raw.order_id ?? raw.id),
    shop_id: Number(raw.shop_id ?? 0),
    shop_name: raw.shop_name ?? '',
    status: String(raw.status ?? raw.order_status ?? 'PENDING').toUpperCase(),
    total_amount: Number(raw.total_amount ?? 0),
    delivery_address: String(raw.delivery_address ?? ''),
    items: Array.isArray(raw.items)
      ? raw.items.map((item: any) => ({
          product_id: Number(item.product_id ?? 0),
          product_name: item.product_name ?? item.name ?? undefined,
          quantity: Number(item.quantity ?? item.qty ?? 0),
          unit_price: Number(item.unit_price ?? item.price ?? 0),
          line_total: Number(item.line_total ?? (Number(item.quantity ?? 0) * Number(item.unit_price ?? item.price ?? 0))),
        }))
      : [],
    created_at: String(raw.created_at ?? new Date().toISOString()),
  };
}

function getStepIndex(status: string) {
  const index = STEPS.indexOf(status as (typeof STEPS)[number]);
  return index < 0 ? 0 : index;
}

function formatDate(value: string) {
  try {
    return new Intl.DateTimeFormat('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function money(value: number) {
  return `₹${value.toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export default function MyOrdersPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [liveNotice, setLiveNotice] = useState('');
  const previousStatusRef = useRef<Map<number, string>>(new Map());

  const fetchOrders = useCallback(async (showLoader = false) => {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace('/auth');
      return;
    }

    if (showLoader) setRefreshing(true);

    try {
      const response = await fetch(`${API_BASE}/store/my-orders`, {
        cache: 'no-store',
        headers: {
          Authorization: `Bearer ${token}`,
          'Cache-Control': 'no-cache',
        },
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem('customerToken');
          router.replace('/auth');
          return;
        }
        throw new Error('Failed to load your orders.');
      }

      const data = await response.json();
      const nextOrders = Array.isArray(data.orders) ? data.orders.map(normalizeOrder) : [];

      // Keep the UI live even though the backend currently exposes REST polling.
      for (const order of nextOrders) {
        const previous = previousStatusRef.current.get(order.order_id);
        if (previous && previous !== order.status) {
          setLiveNotice(`Order #${order.order_id} updated to ${t(`status_${order.status}`) || order.status}.`);
          window.setTimeout(() => setLiveNotice(''), 3200);
          window.dispatchEvent(new CustomEvent('retailmind:order-updated', {
            detail: { orderId: order.order_id, status: order.status },
          }));
        }
      }
      previousStatusRef.current = new Map(
        nextOrders.map((order) => [order.order_id, order.status]),
      );

      setOrders(nextOrders);
      setLastUpdated(new Date());
      setError('');
    } catch (err: any) {
      setError(err?.message || 'Unable to load your orders.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useEffect(() => {
    void fetchOrders();

    const interval = window.setInterval(() => {
      void fetchOrders();
    }, 2500);

    const onFocus = () => void fetchOrders();
    window.addEventListener('focus', onFocus);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener('focus', onFocus);
    };
  }, [fetchOrders]);

  const activeCount = useMemo(
    () => orders.filter((order) => !['DELIVERED', 'REJECTED'].includes(order.status)).length,
    [orders],
  );

  return (
    <main className="container" style={{ padding: '34px 20px 90px', maxWidth: 1080 }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 16,
        marginBottom: 26,
        flexWrap: 'wrap',
      }}>
        <div>
          <button
            onClick={() => router.back()}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)',
              borderRadius: 12,
              padding: '9px 13px',
              color: '#fff',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 7,
              marginBottom: 14,
            }}
          >
            <ArrowLeft size={16} /> {t('orders_back')}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.5rem)', fontWeight: 800, margin: 0 }}>
              {t('orders_title')}
            </h1>
            {activeCount > 0 && (
              <span style={{
                borderRadius: 999,
                background: 'rgba(34,211,238,0.12)',
                color: '#67e8f9',
                border: '1px solid rgba(34,211,238,0.22)',
                padding: '5px 10px',
                fontSize: 12,
                fontWeight: 700,
              }}>
                {activeCount} active
              </span>
            )}
          </div>

          <p style={{ color: 'var(--text-secondary)', margin: '7px 0 0' }}>
            {t('orders_live')}
          </p>
        </div>

        <button
          onClick={() => void fetchOrders(true)}
          disabled={refreshing}
          style={{
            borderRadius: 12,
            padding: '10px 14px',
            border: '1px solid rgba(255,255,255,0.1)',
            background: 'rgba(255,255,255,0.05)',
            color: '#fff',
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            cursor: refreshing ? 'wait' : 'pointer',
          }}
        >
          <RefreshCw size={16} className={refreshing ? 'spin' : ''} />
          {t('orders_refresh')}
        </button>
      </div>

      <AnimatePresence>
        {liveNotice && (
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            style={{
              marginBottom: 14,
              padding: '11px 14px',
              borderRadius: 14,
              border: '1px solid rgba(34,197,94,0.2)',
              background: 'rgba(34,197,94,0.08)',
              color: '#86efac',
              fontSize: 13,
              fontWeight: 700,
            }}
          >
            ✓ {liveNotice}
          </motion.div>
        )}
      </AnimatePresence>

      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        color: 'var(--text-secondary)',
        fontSize: 12,
        marginBottom: 18,
      }}>
        <span style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: activeCount > 0 ? '#22c55e' : '#64748b',
          boxShadow: activeCount > 0 ? '0 0 0 5px rgba(34,197,94,0.08)' : 'none',
        }} />
        {t('orders_live')}
        {lastUpdated ? ` · checked ${lastUpdated.toLocaleTimeString('en-IN')}` : ''}
      </div>

      {loading ? (
        <div style={{ display: 'grid', gap: 18 }}>
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0.3 }}
              animate={{ opacity: [0.35, 0.75, 0.35] }}
              transition={{ duration: 1.4, repeat: Infinity, delay: i * 0.15 }}
              style={{
                height: 300,
                borderRadius: 24,
                background: 'rgba(255,255,255,0.045)',
                border: '1px solid rgba(255,255,255,0.06)',
              }}
            />
          ))}
        </div>
      ) : error ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            padding: 28,
            borderRadius: 20,
            border: '1px solid rgba(248,113,113,0.2)',
            background: 'rgba(127,29,29,0.14)',
          }}
        >
          <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <XCircle size={22} color="#f87171" />
            <div style={{ flex: 1 }}>
              <h2 style={{ fontSize: 18, margin: '0 0 6px' }}>We couldn't load your orders</h2>
              <p style={{ margin: 0, color: 'var(--text-secondary)' }}>{error}</p>
            </div>
            <button
              className="btn-primary"
              onClick={() => void fetchOrders(true)}
              style={{ whiteSpace: 'nowrap' }}
            >
              Try again
            </button>
          </div>
        </motion.div>
      ) : orders.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          style={{
            textAlign: 'center',
            padding: '74px 20px',
            borderRadius: 26,
            background: 'linear-gradient(135deg, rgba(99,102,241,0.10), rgba(34,211,238,0.05))',
            border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <Sparkles size={38} color="#a5b4fc" style={{ marginBottom: 12 }} />
          <h2 style={{ margin: '0 0 8px' }}>{t('orders_empty_title')}</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '0 auto 24px', maxWidth: 470 }}>
            {t('orders_empty_text')}
          </p>
          <button className="btn-primary" onClick={() => router.push('/')}>{t('orders_start')}</button>
        </motion.div>
      ) : (
        <div style={{ display: 'grid', gap: 18 }}>
          <AnimatePresence initial={false}>
            {orders.map((order) => {
              const status = order.status in statusMeta ? order.status : 'PENDING';
              const meta = statusMeta[status];
              const localizedTitle = t(`status_${status}`);
              const localizedDescription = t(`status_${status}_desc`);
              const Icon = meta.icon;
              const currentIndex = getStepIndex(status);
              const rejected = status === 'REJECTED';

              return (
                <motion.article
                  key={order.order_id}
                  layout
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.28 }}
                  style={{
                    overflow: 'hidden',
                    borderRadius: 26,
                    background: 'linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.018))',
                    border: `1px solid ${meta.tone}33`,
                    boxShadow: '0 18px 55px rgba(0,0,0,0.20)',
                  }}
                >
                  <div style={{ padding: 24 }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      gap: 14,
                      alignItems: 'flex-start',
                      flexWrap: 'wrap',
                    }}>
                      <div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12, letterSpacing: 0.5 }}>
                          {order.shop_name || `Shop #${order.shop_id}`}
                        </div>
                        <h2 style={{ margin: '5px 0 6px', fontSize: 20 }}>
                          Order #{order.order_id}
                        </h2>
                        <div style={{ color: 'var(--text-secondary)', fontSize: 12 }}>
                          {formatDate(order.created_at)}
                        </div>
                      </div>

                      <div style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 7,
                        borderRadius: 999,
                        padding: '8px 12px',
                        background: `${meta.tone}14`,
                        color: meta.tone,
                        border: `1px solid ${meta.tone}2b`,
                        fontSize: 12,
                        fontWeight: 800,
                      }}>
                        <Icon size={14} />
                        {meta.title}
                      </div>
                    </div>

                    <div style={{
                      marginTop: 24,
                      padding: '18px 16px',
                      borderRadius: 18,
                      background: 'rgba(0,0,0,0.14)',
                    }}>
                      {rejected ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{
                            width: 42,
                            height: 42,
                            borderRadius: '50%',
                            display: 'grid',
                            placeItems: 'center',
                            background: 'rgba(248,113,113,0.14)',
                            color: '#f87171',
                          }}>
                            <XCircle size={22} />
                          </div>
                          <div>
                            <div style={{ fontWeight: 750 }}>The shop could not complete this order</div>
                            <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginTop: 3 }}>
                              Any reserved stock is restored by the shop system.
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
                          gap: 8,
                        }}>
                          {STEPS.map((step, idx) => {
                            const stepMeta = statusMeta[step];
                            const StepIcon = stepMeta.icon;
                            const done = idx <= currentIndex;
                            const current = idx === currentIndex;

                            return (
                              <div key={step} style={{ minWidth: 0 }}>
                                <div style={{ display: 'flex', alignItems: 'center' }}>
                                  <div style={{
                                    width: 34,
                                    height: 34,
                                    borderRadius: '50%',
                                    display: 'grid',
                                    placeItems: 'center',
                                    flexShrink: 0,
                                    background: done ? `${stepMeta.tone}18` : 'rgba(255,255,255,0.05)',
                                    color: done ? stepMeta.tone : '#64748b',
                                    border: `1px solid ${done ? stepMeta.tone + '46' : 'rgba(255,255,255,0.08)'}`,
                                    boxShadow: current ? `0 0 0 7px ${stepMeta.tone}10` : 'none',
                                  }}>
                                    <StepIcon size={16} />
                                  </div>
                                  {idx < STEPS.length - 1 && (
                                    <div style={{
                                      height: 2,
                                      flex: 1,
                                      margin: '0 7px',
                                      background: idx < currentIndex ? stepMeta.tone : 'rgba(255,255,255,0.08)',
                                    }} />
                                  )}
                                </div>
                                <div style={{
                                  marginTop: 8,
                                  fontSize: 11,
                                  fontWeight: current ? 800 : 650,
                                  color: done ? '#fff' : '#64748b',
                                }}>
                                  {stepMeta.title}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <p style={{ color: 'var(--text-secondary)', fontSize: 13, margin: '14px 2px 22px' }}>
                      {localizedDescription}
                    </p>

                    <div style={{
                      display: 'grid',
                      gap: 9,
                      marginBottom: 18,
                    }}>
                      {order.items.map((item, idx) => (
                        <motion.div
                          key={`${order.order_id}-${item.product_id}-${idx}`}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: idx * 0.04 }}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: 16,
                            padding: '12px 13px',
                            borderRadius: 14,
                            background: 'rgba(255,255,255,0.035)',
                          }}
                        >
                          <div style={{ display: 'flex', gap: 11, minWidth: 0 }}>
                            <div style={{
                              width: 36,
                              height: 36,
                              borderRadius: 11,
                              display: 'grid',
                              placeItems: 'center',
                              background: 'rgba(99,102,241,0.12)',
                              color: '#a5b4fc',
                              flexShrink: 0,
                            }}>
                              <Package size={17} />
                            </div>
                            <div style={{ minWidth: 0 }}>
                              <div style={{ fontWeight: 650, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {item.product_name || `Product #${item.product_id}`}
                              </div>
                              <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginTop: 3 }}>
                                Qty {item.quantity} {item.unit_price ? `· ${money(item.unit_price)} each` : ''}
                              </div>
                            </div>
                          </div>
                          <div style={{ fontWeight: 750, alignSelf: 'center' }}>
                            {money(item.line_total ?? item.unit_price! * item.quantity)}
                          </div>
                        </motion.div>
                      ))}
                    </div>

                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr auto',
                      gap: 18,
                      borderTop: '1px solid rgba(255,255,255,0.08)',
                      paddingTop: 18,
                    }}>
                      <div>
                        <div style={{
                          color: 'var(--text-secondary)',
                          textTransform: 'uppercase',
                          letterSpacing: 0.65,
                          fontSize: 10,
                          fontWeight: 750,
                          marginBottom: 7,
                        }}>
                          {t('delivery_address')}
                        </div>
                        <div style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 7,
                          color: '#e2e8f0',
                          fontSize: 13,
                          lineHeight: 1.45,
                        }}>
                          <MapPin size={15} color="#22d3ee" style={{ marginTop: 2, flexShrink: 0 }} />
                          <span>{order.delivery_address}</span>
                        </div>
                      </div>

                      <div style={{ textAlign: 'right', minWidth: 120 }}>
                        <div style={{
                          color: 'var(--text-secondary)',
                          textTransform: 'uppercase',
                          letterSpacing: 0.65,
                          fontSize: 10,
                          fontWeight: 750,
                          marginBottom: 7,
                        }}>
                          {t('total')}
                        </div>
                        <div style={{
                          fontSize: 24,
                          fontWeight: 850,
                          color: '#67e8f9',
                        }}>
                          {money(order.total_amount)}
                        </div>
                      </div>
                    </div>
                  </div>
                </motion.article>
              );
            })}
          </AnimatePresence>
        </div>
      )}

      <style jsx>{`
        .spin { animation: rm-spin 0.8s linear infinite; }
        @keyframes rm-spin { to { transform: rotate(360deg); } }
        @media (max-width: 720px) {
          main { padding-bottom: 54px !important; }
        }
      `}</style>
    </main>
  );
}
