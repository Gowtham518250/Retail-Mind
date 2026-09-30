'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  Package,
  MapPin,
  Clock,
  CheckCircle2,
  Truck,
  ArrowLeft,
  RefreshCw,
  XCircle,
  CircleDot,
  Wifi,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';

interface OrderItem {
  product_id: number;
  product_name?: string;
  name?: string;
  quantity: number;
  unit_price?: number;
  price?: number;
  line_total?: number;
}

interface Order {
  order_id: number;
  shop_id: number;
  status: string;
  total_amount: number;
  delivery_address: string;
  items: OrderItem[];
  created_at: string;
}

const STATUS_STEPS = ['PENDING', 'ACCEPTED', 'DISPATCHED', 'DELIVERED'] as const;

const STATUS_META: Record<string, {
  label: string;
  description: string;
  icon: typeof Clock;
  tone: string;
}> = {
  PENDING: {
    label: 'Order placed',
    description: 'Waiting for the shop to accept your order.',
    icon: Clock,
    tone: '#facc15',
  },
  ACCEPTED: {
    label: 'Order accepted',
    description: 'The shop accepted your order and is preparing it.',
    icon: CheckCircle2,
    tone: '#22d3ee',
  },
  DISPATCHED: {
    label: 'Out for delivery',
    description: 'Your order has been dispatched.',
    icon: Truck,
    tone: '#818cf8',
  },
  DELIVERED: {
    label: 'Delivered',
    description: 'Your order was delivered successfully.',
    icon: CheckCircle2,
    tone: '#10b981',
  },
  REJECTED: {
    label: 'Order rejected',
    description: 'The shop could not accept this order.',
    icon: XCircle,
    tone: '#f87171',
  },
};

function statusIndex(status: string) {
  return STATUS_STEPS.indexOf(status as (typeof STATUS_STEPS)[number]);
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(value);
}

function OrderTimeline({ status }: { status: string }) {
  const current = statusIndex(status);
  const rejected = status === 'REJECTED';

  return (
    <div className="order-timeline">
      {STATUS_STEPS.map((step, index) => {
        const meta = STATUS_META[step];
        const Icon = meta.icon;
        const completed = !rejected && current >= index;
        const active = !rejected && current === index;

        return (
          <div className="timeline-step" key={step}>
            <div
              className={[
                'timeline-node',
                completed ? 'completed' : '',
                active ? 'active' : '',
              ].join(' ')}
              style={completed ? { borderColor: meta.tone, color: meta.tone } : undefined}
            >
              {completed ? <Icon size={15} /> : <CircleDot size={12} />}
            </div>

            <div className="timeline-copy">
              <div className="timeline-label">{meta.label}</div>
              {active && <div className="timeline-description">{meta.description}</div>}
            </div>

            {index < STATUS_STEPS.length - 1 && (
              <div className={`timeline-line ${!rejected && current > index ? 'filled' : ''}`} />
            )}
          </div>
        );
      })}

      {rejected && (
        <div className="rejected-banner">
          <XCircle size={17} />
          <div>
            <strong>{STATUS_META.REJECTED.label}</strong>
            <span>{STATUS_META.REJECTED.description}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function MyOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const router = useRouter();

  const fetchOrders = useCallback(async (silent = false) => {
    const token = localStorage.getItem('customerToken');

    if (!token) {
      router.push('/auth');
      return;
    }

    if (silent) setRefreshing(true);

    try {
      const response = await fetch(`${API_BASE}/store/my-orders`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: 'no-store',
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem('customerToken');
          router.push('/auth');
          return;
        }
        throw new Error('Failed to load orders');
      }

      const data = await response.json();
      setOrders(Array.isArray(data.orders) ? data.orders : []);
      setError('');
      setLastUpdated(new Date());
    } catch (err: any) {
      // Keep the existing order list during a transient network failure.
      // This prevents the realtime refresh from turning the page blank.
      setError(err?.message || 'Unable to refresh orders right now.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [router]);

  useEffect(() => {
    void fetchOrders();

    // Fast fallback realtime channel: the current backend exposes REST
    // status endpoints but no customer WebSocket/SSE stream. Polling every
    // 5 seconds keeps the customer account visibly in sync with owner actions
    // without requiring a manual refresh.
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void fetchOrders(true);
      }
    }, 5000);

    const onVisible = () => {
      if (document.visibilityState === 'visible') void fetchOrders(true);
    };

    document.addEventListener('visibilitychange', onVisible);

    return () => {
      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [fetchOrders]);

  const activeCount = useMemo(
    () => orders.filter((order) => !['DELIVERED', 'REJECTED'].includes(order.status)).length,
    [orders]
  );

  return (
    <div className="container orders-page" style={{ padding: '40px 20px 64px' }}>
      <div className="orders-page-header">
        <div className="orders-title-row">
          <button
            onClick={() => router.back()}
            className="orders-back-btn"
            aria-label="Go back"
          >
            <ArrowLeft size={16} /> Back
          </button>

          <div>
            <div className="orders-eyebrow">Customer account</div>
            <h1 className="orders-title">My Orders</h1>
            <p className="orders-subtitle">
              {activeCount > 0
                ? `${activeCount} order${activeCount === 1 ? '' : 's'} currently in progress`
                : 'Track your purchases and delivery progress'}
            </p>
          </div>
        </div>

        <div className="orders-live-status" aria-live="polite">
          <span className="live-dot" />
          <Wifi size={14} />
          Live updates
          <button
            className="refresh-orders-btn"
            onClick={() => void fetchOrders(true)}
            disabled={refreshing}
            title="Refresh orders"
          >
            <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
          </button>
        </div>
      </div>

      {lastUpdated && !loading && (
        <div className="orders-last-updated">
          Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
        </div>
      )}

      {loading ? (
        <div className="orders-skeleton-list">
          {[1, 2, 3].map((i) => (
            <div key={i} className="order-skeleton-card">
              <div className="order-skeleton-line long" />
              <div className="order-skeleton-line medium" />
              <div className="order-skeleton-block" />
            </div>
          ))}
        </div>
      ) : error && orders.length === 0 ? (
        <div className="orders-error-card">
          <XCircle size={22} />
          <h2>We couldn't load your orders</h2>
          <p>{error}</p>
          <button className="btn-primary" onClick={() => void fetchOrders(true)}>
            Try again
          </button>
        </div>
      ) : orders.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="orders-empty-card"
        >
          <div className="orders-empty-icon"><Package size={30} /></div>
          <h2>No orders yet</h2>
          <p>Looks like you haven't placed any orders. Start shopping to see your purchases here.</p>
          <button className="btn-primary" onClick={() => router.push('/')}>
            Start Shopping
          </button>
        </motion.div>
      ) : (
        <>
          {error && (
            <div className="orders-sync-warning" role="status">
              <RefreshCw size={15} />
              {error} Showing your last known orders.
            </div>
          )}

          <div className="orders-list">
            {orders.map((order, orderIndex) => {
              const meta = STATUS_META[order.status] || STATUS_META.PENDING;
              const Icon = meta.icon;

              return (
                <motion.article
                  key={order.order_id}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: Math.min(orderIndex * 0.06, 0.3) }}
                  className="order-card"
                >
                  <div className="order-card-glow" />

                  <div className="order-card-header">
                    <div>
                      <div className="order-number-row">
                        <span className="order-number">Order #{order.order_id}</span>
                        <span className="order-status-pill" style={{ color: meta.tone, borderColor: `${meta.tone}55`, background: `${meta.tone}14` }}>
                          <Icon size={14} />
                          {meta.label}
                        </span>
                      </div>
                      <div className="order-created">
                        <Clock size={13} />
                        {new Date(order.created_at).toLocaleString()}
                      </div>
                    </div>

                    <div className="order-total-badge">
                      <span>Total</span>
                      <strong>{formatCurrency(order.total_amount)}</strong>
                    </div>
                  </div>

                  <OrderTimeline status={order.status} />

                  <div className="order-section">
                    <div className="order-section-title">Items</div>
                    <div className="order-items-grid">
                      {order.items.map((item, idx) => {
                        const name = item.product_name || item.name || `Product #${item.product_id}`;
                        const unitPrice = Number(item.unit_price ?? item.price ?? 0);
                        const lineTotal = Number(item.line_total ?? unitPrice * item.quantity);

                        return (
                          <div className="order-item-row" key={`${item.product_id}-${idx}`}>
                            <div className="order-item-icon"><Package size={16} /></div>
                            <div className="order-item-main">
                              <strong>{name}</strong>
                              <span>Quantity × {item.quantity}</span>
                            </div>
                            <div className="order-item-price">
                              <span>{formatCurrency(unitPrice)}</span>
                              <strong>{formatCurrency(lineTotal)}</strong>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="order-card-footer">
                    <div className="order-address">
                      <div className="order-section-title">Delivery address</div>
                      <div className="order-address-row">
                        <MapPin size={16} />
                        <span>{order.delivery_address}</span>
                      </div>
                    </div>

                    <div className="order-footer-status">
                      <span>Current status</span>
                      <strong style={{ color: meta.tone }}>{order.status}</strong>
                    </div>
                  </div>
                </motion.article>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
