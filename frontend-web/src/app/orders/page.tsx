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
  Search,
  ChevronDown,
  ChevronUp,
  ShoppingBag,
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
  const [liveConnected, setLiveConnected] = useState(false);
  const [filter, setFilter] = useState<'ALL' | 'ACTIVE' | 'DELIVERED' | 'REJECTED'>('ALL');
  const [query, setQuery] = useState('');
  const [expandedOrders, setExpandedOrders] = useState<Set<number>>(new Set());
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

    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectDelayMs = 1000;

    const scheduleReconnect = () => {
      if (stopped || reconnectTimer !== null) return;

      const delay = reconnectDelayMs;
      reconnectDelayMs = Math.min(reconnectDelayMs * 2, 30000);

      reconnectTimer = window.setTimeout(() => {
        reconnectTimer = null;
        void connectRealtime();
      }, delay);
    };

    const connectRealtime = async () => {
      if (stopped) return;

      try {
        const token = localStorage.getItem('customerToken');
        if (!token) {
          stopped = true;
          router.push('/auth');
          return;
        }

        const ticketResponse = await fetch(
          `${API_BASE}/api/ws/token?shop_id=0`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: 'no-store',
          }
        );

        if (!ticketResponse.ok) {
          if (ticketResponse.status === 401 || ticketResponse.status === 403) {
            stopped = true;
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return;
          }
          throw new Error('Realtime ticket request failed');
        }

        const ticketData = await ticketResponse.json();
        const wsBase = API_BASE
          .replace(/^https:/, 'wss:')
          .replace(/^http:/, 'ws:');

        const wsUrl =
          `${wsBase}/api/ws/live/${encodeURIComponent(ticketData.user_id)}/${encodeURIComponent(ticketData.shop_id)}?ticket=${encodeURIComponent(ticketData.token)}`;

        socket = new WebSocket(wsUrl);

        socket.onopen = () => {
          if (stopped) return;
          reconnectDelayMs = 1000;
          setLiveConnected(true);
        };

        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data);

            if (event?.type === 'order.status_changed') {
              const orderId = Number(event.order_id);
              const nextStatus = String(event.status || '').toUpperCase();

              setOrders((current) =>
                current.map((order) =>
                  order.order_id === orderId
                    ? { ...order, status: nextStatus }
                    : order
                )
              );
              setError('');
              setLastUpdated(new Date());
            } else if (event?.type === 'order.created') {
              // A new order is already persisted; REST reconciliation gives the
              // customer the complete new order payload and keeps ordering stable.
              void fetchOrders(true);
            }
          } catch {
            // Ignore malformed realtime payloads; the REST fallback remains authoritative.
          }
        };

        socket.onerror = () => {
          setLiveConnected(false);
        };

        socket.onclose = () => {
          setLiveConnected(false);
          socket = null;
          scheduleReconnect();
        };
      } catch {
        setLiveConnected(false);
        scheduleReconnect();
      }
    };

    void connectRealtime();

    // Deployment-safe fallback: REST reconciliation runs less frequently because
    // the WebSocket is the primary update path.
    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void fetchOrders(true);
      }
    }, 30000);

    const onVisible = () => {
      if (document.visibilityState === 'visible') void fetchOrders(true);
    };

    document.addEventListener('visibilitychange', onVisible);

    return () => {
      stopped = true;
      setLiveConnected(false);

      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      if (socket) {
        try {
          socket.close();
        } catch {
          // ignore cleanup errors
        }
        socket = null;
      }

      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [fetchOrders, router]);

  const activeCount = useMemo(
    () => orders.filter((order) => !['DELIVERED', 'REJECTED'].includes(order.status)).length,
    [orders]
  );

  const deliveredCount = useMemo(
    () => orders.filter((order) => order.status === 'DELIVERED').length,
    [orders]
  );

  const totalSpent = useMemo(
    () => orders.reduce((sum, order) => sum + Number(order.total_amount || 0), 0),
    [orders]
  );

  const visibleOrders = useMemo(() => {
    const q = query.trim().toLowerCase();
    return orders.filter((order) => {
      const filterMatch =
        filter === 'ALL' ||
        (filter === 'ACTIVE' && !['DELIVERED', 'REJECTED'].includes(order.status)) ||
        (filter === 'DELIVERED' && order.status === 'DELIVERED') ||
        (filter === 'REJECTED' && order.status === 'REJECTED');
      const queryMatch =
        !q ||
        String(order.order_id).includes(q) ||
        order.items.some((item) =>
          String(item.product_name || item.name || '').toLowerCase().includes(q)
        );
      return filterMatch && queryMatch;
    });
  }, [orders, filter, query]);

  const toggleOrder = (orderId: number) => {
    setExpandedOrders((current) => {
      const next = new Set(current);
      next.has(orderId) ? next.delete(orderId) : next.add(orderId);
      return next;
    });
  };

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
          <span className={`live-dot ${liveConnected ? '' : 'offline'}`} />
          <Wifi size={14} />
          {liveConnected ? 'Live updates' : 'Reconnecting…'}
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
    <div className="orders-fk-page">
      <div className="orders-fk-shell">
        <header className="orders-fk-topbar">
          <div className="orders-fk-brand">
            <button className="orders-fk-back" onClick={() => router.back()} aria-label="Go back"><ArrowLeft size={18} /></button>
            <div><div className="orders-fk-brand-title">My Orders</div><div className="orders-fk-brand-subtitle">Track every purchase in one place</div></div>
          </div>
          <div className="orders-fk-live">
            <span className={`orders-fk-live-dot ${liveConnected ? '' : 'offline'}`} />
            <Wifi size={15} /> {liveConnected ? 'Live updates' : 'Reconnecting'}
            <button className="orders-fk-refresh" onClick={() => void fetchOrders(true)} disabled={refreshing} title="Refresh orders">
              <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
            </button>
          </div>
        </header>

        <section className="orders-fk-stats">
          <div className="orders-fk-stat"><span>Total orders</span><strong>{orders.length}</strong></div>
          <div className="orders-fk-stat"><span>In progress</span><strong>{activeCount}</strong></div>
          <div className="orders-fk-stat"><span>Delivered</span><strong>{deliveredCount}</strong></div>
          <div className="orders-fk-stat"><span>Total spent</span><strong>{formatCurrency(totalSpent)}</strong></div>
        </section>

        <section className="orders-fk-toolbar">
          <div className="orders-fk-tabs" role="tablist" aria-label="Order filters">
            {([
              ['ALL', 'All orders'],
              ['ACTIVE', 'Active'],
              ['DELIVERED', 'Delivered'],
              ['REJECTED', 'Cancelled'],
            ] as const).map(([value, label]) => (
              <button key={value} className={`orders-fk-tab ${filter === value ? 'active' : ''}`} onClick={() => setFilter(value)}>{label}</button>
            ))}
          </div>
          <label className="orders-fk-search">
            <Search size={17} />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search order number or product" aria-label="Search orders" />
          </label>
        </section>

        {lastUpdated && !loading && (
          <div className="orders-fk-updated">Last updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
        )}

        {loading ? (
          <div className="orders-fk-list">
            {[1, 2, 3].map((i) => (
              <div key={i} className="orders-fk-skeleton"><div className="sk-line wide" /><div className="sk-line medium" /><div className="sk-block" /></div>
            ))}
          </div>
        ) : error && orders.length === 0 ? (
          <div className="orders-fk-empty">
            <div className="orders-fk-empty-icon"><XCircle size={30} /></div>
            <h2>We couldn't load your orders</h2><p>{error}</p>
            <button className="orders-fk-primary-btn" onClick={() => void fetchOrders(true)}>Try again</button>
          </div>
        ) : visibleOrders.length === 0 ? (
          <div className="orders-fk-empty">
            <div className="orders-fk-empty-icon"><ShoppingBag size={30} /></div>
            <h2>{orders.length === 0 ? 'No orders yet' : 'No matching orders'}</h2>
            <p>{orders.length === 0 ? 'Place your first order and it will appear here with live tracking.' : 'Try another filter or search term.'}</p>
            {orders.length === 0 && <button className="orders-fk-primary-btn" onClick={() => router.push('/')}>Start Shopping</button>}
          </div>
        ) : (
          <>
            {error && <div className="orders-fk-warning" role="status"><RefreshCw size={15} /> {error} Showing your last known orders.</div>}
            <div className="orders-fk-list">
              {visibleOrders.map((order, orderIndex) => {
                const meta = STATUS_META[order.status] || STATUS_META.PENDING;
                const Icon = meta.icon;
                const isOpen = expandedOrders.has(order.order_id);
                const firstItem = order.items[0];
                const firstName = firstItem?.product_name || firstItem?.name || (firstItem ? `Product #${firstItem.product_id}` : 'Order items');
                return (
                  <motion.article
                    key={order.order_id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25, delay: Math.min(orderIndex * 0.04, 0.2) }}
                    className="orders-fk-card"
                  >
                    <div className="orders-fk-card-top">
                      <div><div className="orders-fk-order-number">Order #{order.order_id}</div><div className="orders-fk-order-date">{new Date(order.created_at).toLocaleString('en-IN')}</div></div>
                      <div className="orders-fk-card-total"><span>Order total</span><strong>{formatCurrency(order.total_amount)}</strong></div>
                    </div>
                    <div className="orders-fk-item-preview">
                      <div className="orders-fk-product-icon"><Package size={24} /></div>
                      <div className="orders-fk-item-copy"><strong>{firstName}</strong><span>{order.items.length === 1 ? `Qty ${order.items[0].quantity}` : `${order.items.length} items`}</span></div>
                      <span className={`orders-fk-status ${order.status.toLowerCase()}`}><Icon size={14} /> {meta.label}</span>
                    </div>
                    <OrderTimeline status={order.status} />
                    <div className="orders-fk-card-actions">
                      <div className="orders-fk-delivery"><MapPin size={16} /><span>{order.delivery_address}</span></div>
                      <button className="orders-fk-details-btn" onClick={() => toggleOrder(order.order_id)}>{isOpen ? 'Hide details' : 'View details'}{isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</button>
                    </div>
                    {isOpen && (
                      <div className="orders-fk-details">
                        <div className="orders-fk-details-grid">
                          <div><span>Delivery address</span><strong>{order.delivery_address}</strong></div>
                          <div><span>Current status</span><strong>{meta.label}</strong></div>
                          <div><span>Shop</span><strong>#{order.shop_id}</strong></div>
                          <div><span>Items</span><strong>{order.items.length}</strong></div>
                        </div>
                        <div className="orders-fk-items">
                          {order.items.map((item, idx) => {
                            const name = item.product_name || item.name || `Product #${item.product_id}`;
                            const unitPrice = Number(item.unit_price ?? item.price ?? 0);
                            const lineTotal = Number(item.line_total ?? unitPrice * item.quantity);
                            return (
                              <div className="orders-fk-detail-item" key={`${item.product_id}-${idx}`}>
                                <div className="orders-fk-product-icon small"><Package size={18} /></div>
                                <div className="orders-fk-detail-name"><strong>{name}</strong><span>Qty {item.quantity} · {formatCurrency(unitPrice)} each</span></div>
                                <strong>{formatCurrency(lineTotal)}</strong>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </motion.article>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}