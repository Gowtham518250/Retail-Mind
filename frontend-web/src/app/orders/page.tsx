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
  Star,
  Ban,
  RotateCcw,
  Sparkles,
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

interface OrderReview {
  rating: number;
  comment?: string | null;
  created_at?: string | null;
}

interface ReturnRequest {
  id: number;
  status: string;
  reason: string;
  refund_amount: number;
  stock_restored?: boolean;
  created_at?: string | null;
  processed_at?: string | null;
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
  review?: OrderReview | null;
  can_cancel?: boolean;
  return_request?: ReturnRequest | null;
}

const STATUS_STEPS = ['PENDING', 'ACCEPTED', 'DISPATCHED', 'DELIVERED'] as const;

const STATUS_META: Record<
  string,
  {
    label: string;
    description: string;
    icon: typeof Clock;
    tone: string;
  }
> = {
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
    description: 'Your order is on the way.',
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
    label: 'Rejected by shop',
    description: 'The shop could not accept this order.',
    icon: XCircle,
    tone: '#f87171',
  },
  CANCELLED: {
    label: 'Cancelled',
    description: 'This order was cancelled before dispatch.',
    icon: Ban,
    tone: '#fb7185',
  },
  RETURNED: {
    label: 'Returned',
    description: 'The shop accepted the return and reversed the online sale.',
    icon: RotateCcw,
    tone: '#a78bfa',
  },
};

const TERMINAL_STATUSES = ['DELIVERED', 'REJECTED', 'CANCELLED', 'RETURNED'];
const REVERSIBLE_STATUSES = ['PENDING', 'ACCEPTED'];

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

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function activeReturnRequest(order: Order) {
  const status = String(order.return_request?.status || '').toUpperCase();
  return Boolean(
    order.return_request &&
      status !== 'REJECTED',
  );
}

function returnLabel(order: Order) {
  const status = String(order.return_request?.status || '').toUpperCase();
  if (order.status === 'RETURNED' || status === 'REFUND_PENDING' || status === 'REFUNDED') {
    return 'Return complete';
  }
  if (status === 'REQUESTED') return 'Return requested';
  return 'Return in progress';
}

function OrderTimeline({ status }: { status: string }) {
  const current = statusIndex(status);
  const terminal = !STATUS_STEPS.includes(status as (typeof STATUS_STEPS)[number]);
  if (terminal) {
    const meta = STATUS_META[status] || STATUS_META.REJECTED;
    const Icon = meta.icon;
    return (
      <div className="rejected-banner">
        <Icon size={17} />
        <div>
          <strong>{meta.label}</strong>
          <span>{meta.description}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="order-timeline">
      {STATUS_STEPS.map((step, index) => {
        const meta = STATUS_META[step];
        const Icon = meta.icon;
        const completed = current >= index;
        const active = current === index;

        return (
          <div className="timeline-step" key={step}>
            <div
              className={
                'timeline-node ' +
                (completed ? 'completed ' : '') +
                (active ? 'active' : '')
              }
              style={
                completed
                  ? { borderColor: meta.tone, color: meta.tone }
                  : undefined
              }
            >
              {completed ? <Icon size={15} /> : <CircleDot size={12} />}
            </div>

            <div className="timeline-copy">
              <div className="timeline-label">{meta.label}</div>
              {active && (
                <div className="timeline-description">{meta.description}</div>
              )}
            </div>

            {index < STATUS_STEPS.length - 1 && (
              <div
                className={
                  'timeline-line ' +
                  (current > index ? 'filled' : '')
                }
              />
            )}
          </div>
        );
      })}

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
  const [filter, setFilter] = useState<
    'ALL' | 'ACTIVE' | 'DELIVERED' | 'RETURNED' | 'CANCELLED'
  >('ALL');
  const [query, setQuery] = useState('');
  const [expandedOrders, setExpandedOrders] = useState<Set<number>>(new Set());
  const [returningOrderId, setReturningOrderId] = useState<number | null>(null);
  const [cancelingOrderId, setCancelingOrderId] = useState<number | null>(null);
  const [reviewingOrderId, setReviewingOrderId] = useState<number | null>(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [deliveryByOrder, setDeliveryByOrder] = useState<Record<number, any>>({});
  const [deliveryLoadingId, setDeliveryLoadingId] = useState<number | null>(null);
  const router = useRouter();

  const fetchOrders = useCallback(
    async (silent = false) => {
      const token = localStorage.getItem('customerToken');

      if (!token) {
        router.push('/auth');
        return;
      }

      if (silent) setRefreshing(true);

      try {
        const response = await fetch(API_BASE + '/store/my-orders', {
          headers: { Authorization: 'Bearer ' + token },
          cache: 'no-store',
        });

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return;
          }
          throw new Error('Unable to load your orders right now.');
        }

        const data = await response.json();
        setOrders(Array.isArray(data.orders) ? data.orders : []);
        setError('');
        setLastUpdated(new Date());
      } catch (err: any) {
        setError(err?.message || 'Unable to refresh orders right now.');
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [router],
  );

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
          API_BASE + '/api/ws/token?shop_id=0',
          {
            headers: { Authorization: 'Bearer ' + token },
            cache: 'no-store',
          },
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
          wsBase +
          '/api/ws/live/' +
          encodeURIComponent(ticketData.user_id) +
          '/' +
          encodeURIComponent(ticketData.shop_id) +
          '?ticket=' +
          encodeURIComponent(ticketData.token);

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
                    ? {
                        ...order,
                        status: nextStatus,
                        can_cancel: ['PENDING', 'ACCEPTED'].includes(nextStatus),
                        total_amount: Number(event.total_amount ?? order.total_amount),
                        delivery_address: event.delivery_address || order.delivery_address,
                        items: Array.isArray(event.items) ? event.items : order.items,
                      }
                    : order,
                ),
              );
              setError('');
              setLastUpdated(new Date());
            } else if (event?.type === 'order.created') {
              void fetchOrders(true);
            }
          } catch {
            // REST reconciliation remains authoritative.
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

    const interval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void fetchOrders(true);
      }
    }, 30000);

    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        void fetchOrders(true);
      }
    };

    document.addEventListener('visibilitychange', onVisible);

    return () => {
      stopped = true;
      setLiveConnected(false);

      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
      }

      if (socket) {
        try {
          socket.close();
        } catch {
          // ignore cleanup errors
        }
      }

      window.clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [fetchOrders, router]);

  const activeCount = useMemo(
    () => orders.filter((order) => !TERMINAL_STATUSES.includes(order.status)).length,
    [orders],
  );

  const returnedCount = useMemo(
    () => orders.filter((order) => activeReturnRequest(order)).length,
    [orders],
  );

  const cancelledCount = useMemo(
    () => orders.filter((order) => ['CANCELLED', 'REJECTED'].includes(order.status)).length,
    [orders],
  );

  const deliveredCount = useMemo(
    () => orders.filter((order) => order.status === 'DELIVERED').length,
    [orders],
  );

  const totalSpent = useMemo(
    () =>
      orders.reduce(
        (sum, order) =>
          ['CANCELLED', 'REJECTED', 'RETURNED'].includes(order.status)
            ? sum
            : sum + Number(order.total_amount || 0),
        0,
      ),
    [orders],
  );

  const visibleOrders = useMemo(() => {
    const q = query.trim().toLowerCase();

    return orders.filter((order) => {
      const filterMatch =
        filter === 'ALL' ||
        (filter === 'ACTIVE' &&
          !TERMINAL_STATUSES.includes(order.status)) ||
        (filter === 'DELIVERED' && order.status === 'DELIVERED') ||
        (filter === 'RETURNED' && activeReturnRequest(order)) ||
        (filter === 'CANCELLED' &&
          ['CANCELLED', 'REJECTED'].includes(order.status));

      const queryMatch =
        !q ||
        String(order.order_id).includes(q) ||
        order.items.some((item) =>
          String(item.product_name || item.name || '')
            .toLowerCase()
            .includes(q),
        );

      return filterMatch && queryMatch;
    });
  }, [orders, filter, query]);

  const toggleOrder = async (orderId: number) => {
    const willOpen = !expandedOrders.has(orderId);
    setExpandedOrders((current) => {
      const next = new Set(current);
      if (next.has(orderId)) next.delete(orderId);
      else next.add(orderId);
      return next;
    });

    if (!willOpen || deliveryByOrder[orderId] || deliveryLoadingId === orderId) {
      return;
    }

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    setDeliveryLoadingId(orderId);
    try {
      const response = await fetch(
        API_BASE + '/store/orders/' + orderId + '/delivery',
        {
          headers: { Authorization: 'Bearer ' + token },
          cache: 'no-store',
        },
      );
      if (response.ok) {
        const data = await response.json();
        setDeliveryByOrder((current) => ({ ...current, [orderId]: data }));
      }
    } catch {
      // The main order timeline remains authoritative.
    } finally {
      setDeliveryLoadingId(null);
    }
  };
  const cancelOrder = async (order: Order) => {
    const canCancel =
      order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status);
    if (!canCancel || cancelingOrderId !== null) return;

    const confirmed = window.confirm(
      'Cancel Order #' +
        order.order_id +
        '? Reserved stock will be released and the online order will be closed.',
    );
    if (!confirmed) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    setCancelingOrderId(order.order_id);
    try {
      const response = await fetch(
        API_BASE + '/store/order/' + order.order_id + '/cancel',
        {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token },
          cache: 'no-store',
        },
      );
      const data = await response.json().catch(() => ({}));

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('customerToken');
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to cancel this order.');
      }

      setError('Order #' + order.order_id + ' was cancelled successfully.');
      await fetchOrders(true);
    } catch (err: any) {
      setError(err?.message || 'Unable to cancel this order.');
    } finally {
      setCancelingOrderId(null);
    }
  };

  const requestReturn = async (order: Order) => {
    if (order.status !== 'DELIVERED' || returningOrderId !== null) return;
    const reason = window.prompt(
      'Tell the shop why you want to return this order:',
      '',
    )?.trim();

    if (!reason) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    setReturningOrderId(order.order_id);
    try {
      const response = await fetch(API_BASE + '/store/returns', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: 'Bearer ' + token,
        },
        body: JSON.stringify({
          order_id: order.order_id,
          reason,
        }),
      });

      const data = await response.json();

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('customerToken');
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        throw new Error(
          data?.detail || 'Unable to submit the return request.',
        );
      }

      setError(
        'Return request submitted for Order #' +
          order.order_id +
          '. The shop will review it.',
      );
    } catch (err: any) {
      setError(err?.message || 'Unable to submit the return request.');
    } finally {
      setReturningOrderId(null);
    }
  };

  const submitReview = async (order: Order) => {
    if (
      order.status !== 'DELIVERED' ||
      order.review ||
      reviewingOrderId !== order.order_id
    ) {
      return;
    }

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    try {
      const response = await fetch(
        API_BASE + '/store/order/' + order.order_id + '/rating',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + token,
          },
          body: JSON.stringify({
            rating: reviewRating,
            comment: reviewComment.trim() || null,
          }),
        },
      );
      const data = await response.json().catch(() => ({}));

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('customerToken');
        router.push('/auth');
        return;
      }

      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to save your review.');
      }

      setError('Thanks! Your verified review is now visible on the shop.');
      setReviewingOrderId(null);
      setReviewComment('');
      setReviewRating(5);
      await fetchOrders(true);
    } catch (err: any) {
      setError(err?.message || 'Unable to save your review.');
    }
  };



  return (
    <div className="orders-fk-page">
      <div className="orders-fk-shell">
        <header className="orders-fk-topbar">
          <div className="orders-fk-brand">
            <button
              className="orders-fk-back"
              onClick={() => router.back()}
              aria-label="Go back"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <div className="orders-fk-brand-title">My Orders</div>
              <div className="orders-fk-brand-subtitle">
                Track every purchase in one place
              </div>
            </div>
          </div>

          <div className="orders-fk-live">
            <span
              className={
                'orders-fk-live-dot ' + (liveConnected ? '' : 'offline')
              }
            />
            <Wifi size={15} />
            {liveConnected ? 'Live updates' : 'Reconnecting'}
            <button
              className="orders-fk-refresh"
              onClick={() => void fetchOrders(true)}
              disabled={refreshing}
              title="Refresh orders"
            >
              <RefreshCw
                size={15}
                className={refreshing ? 'spin' : ''}
              />
            </button>
          </div>
        </header>

        <section className="orders-fk-stats">
          <div className="orders-fk-stat">
            <span>Total orders</span>
            <strong>{orders.length}</strong>
          </div>
          <div className="orders-fk-stat">
            <span>In progress</span>
            <strong>{activeCount}</strong>
          </div>
          <div className="orders-fk-stat">
            <span>Delivered</span>
            <strong>{deliveredCount}</strong>
          </div>
          <div className="orders-fk-stat">
            <span>Returned</span>
            <strong>{returnedCount}</strong>
          </div>
          <div className="orders-fk-stat">
            <span>Cancelled</span>
            <strong>{cancelledCount}</strong>
          </div>
          <div className="orders-fk-stat">
            <span>Net spent</span>
            <strong>{formatCurrency(totalSpent)}</strong>
          </div>
        </section>

        <section className="orders-fk-toolbar">
          <div
            className="orders-fk-tabs"
            role="tablist"
            aria-label="Order filters"
          >
            {([
              ['ALL', 'All orders'],
              ['ACTIVE', 'Active'],
              ['DELIVERED', 'Delivered'],
              ['RETURNED', 'Returned'],
              ['CANCELLED', 'Cancelled'],
            ] as const).map(([value, label]) => (
              <button
                key={value}
                className={
                  'orders-fk-tab ' + (filter === value ? 'active' : '')
                }
                onClick={() => setFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>

          <label className="orders-fk-search">
            <Search size={17} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search order number or product"
              aria-label="Search orders"
            />
          </label>
        </section>

        {lastUpdated && !loading && (
          <div className="orders-fk-updated">
            Last updated{' '}
            {lastUpdated.toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        )}

        {loading ? (
          <div className="orders-fk-list">
            {[1, 2, 3].map((i) => (
              <div key={i} className="orders-fk-skeleton">
                <div className="sk-line wide" />
                <div className="sk-line medium" />
                <div className="sk-block" />
              </div>
            ))}
          </div>
        ) : error && orders.length === 0 ? (
          <div className="orders-fk-empty">
            <div className="orders-fk-empty-icon">
              <XCircle size={30} />
            </div>
            <h2>We couldn't load your orders</h2>
            <p>{error}</p>
            <button
              className="orders-fk-primary-btn"
              onClick={() => void fetchOrders(true)}
            >
              Try again
            </button>
          </div>
        ) : visibleOrders.length === 0 ? (
          <div className="orders-fk-empty">
            <div className="orders-fk-empty-icon">
              <ShoppingBag size={30} />
            </div>
            <h2>{orders.length === 0 ? 'No orders yet' : 'No matching orders'}</h2>
            <p>
              {orders.length === 0
                ? 'Place your first order and it will appear here with live tracking.'
                : 'Try another filter or search term.'}
            </p>
            {orders.length === 0 && (
              <button
                className="orders-fk-primary-btn"
                onClick={() => router.push('/')}
              >
                Start Shopping
              </button>
            )}
          </div>
        ) : (
          <>
            {error && (
              <div className="orders-fk-warning" role="status">
                <RefreshCw size={15} />
                {error} Showing your last known orders.
              </div>
            )}

            <div className="orders-fk-list">
              {visibleOrders.map((order, orderIndex) => {
                const meta = STATUS_META[order.status] || STATUS_META.PENDING;
                const returnActive = activeReturnRequest(order);
                const effectiveStatus =
                  returnActive && order.status === 'DELIVERED'
                    ? 'RETURN_REQUESTED'
                    : order.status;
                const effectiveMeta =
                  effectiveStatus === 'RETURN_REQUESTED'
                    ? {
                        label: returnLabel(order),
                        description:
                          order.return_request?.status === 'REQUESTED'
                            ? 'Your return request is waiting for the shop to review it.'
                            : 'Your return request is being processed.',
                        icon: RotateCcw,
                        tone: '#8b5cf6',
                      }
                    : meta;
                const Icon = effectiveMeta.icon;
                const isOpen = expandedOrders.has(order.order_id);
                const firstItem = order.items[0];
                const firstName =
                  firstItem?.product_name ||
                  firstItem?.name ||
                  (firstItem
                    ? 'Product #' + firstItem.product_id
                    : 'Order items');

                return (
                  <motion.article
                    key={order.order_id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: 0.25,
                      delay: Math.min(orderIndex * 0.04, 0.2),
                    }}
                    className="orders-fk-card"
                  >
                    <div className="orders-fk-card-top">
                      <div>
                        <div className="orders-fk-order-number">
                          Order #{order.order_id}
                        </div>
                        <div className="orders-fk-order-date">
                          {formatDate(order.created_at)}
                        </div>
                      </div>
                      <div className="orders-fk-card-total">
                        <span>Order total</span>
                        <strong>{formatCurrency(order.total_amount)}</strong>
                      </div>
                    </div>

                    <div className="orders-fk-item-preview">
                      <div className="orders-fk-product-icon">
                        <Package size={24} />
                      </div>
                      <div className="orders-fk-item-copy">
                        <strong>{firstName}</strong>
                        <span>
                          {order.items.length === 1
                            ? 'Qty ' + order.items[0].quantity
                            : order.items.length + ' items'}
                        </span>
                      </div>
                      <span
                        className={
                          'orders-fk-status ' +
                          order.status.toLowerCase()
                        }
                      >
                        <Icon size={14} /> {meta.label}
                      </span>
                    </div>

                    {effectiveStatus === 'RETURN_REQUESTED' ? (
  <div className="orders-fk-return-state">
    <div className="orders-fk-return-state-icon"><RotateCcw size={15} /></div>
    <div>
      <strong>{effectiveMeta.label}</strong>
      <span>
        {order.return_request?.reason || 'Return request submitted.'}
        {order.return_request?.refund_amount
          ? ' · Refund ' + formatCurrency(order.return_request.refund_amount)
          : ''}
      </span>
    </div>
    <span className="orders-fk-return-state-badge">
      {String(order.return_request?.status || 'REQUESTED').replaceAll('_', ' ')}
    </span>
  </div>
) : (
  <OrderTimeline status={order.status} />
)}

                    <div className="orders-fk-card-actions">
                      <div className="orders-fk-delivery">
                        <MapPin size={16} />
                        <span>{order.delivery_address}</span>
                      </div>
                      <div className="orders-fk-details-actions">
                        {(order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status)) && (
                          <button
                            className="orders-fk-details-btn danger"
                            onClick={() => void cancelOrder(order)}
                            disabled={cancelingOrderId === order.order_id}
                          >
                            {cancelingOrderId === order.order_id ? 'Cancelling…' : 'Cancel order'}
                            <Ban size={14} />
                          </button>
                        )}
                        {order.status === 'DELIVERED' && !order.review && (
                          <button
                            className="orders-fk-details-btn review"
                            onClick={() => {
                              setReviewingOrderId(order.order_id);
                              setReviewRating(5);
                              setReviewComment('');
                              if (!expandedOrders.has(order.order_id)) {
                                setExpandedOrders((current) => new Set(current).add(order.order_id));
                              }
                            }}
                          >
                            Rate & review <Star size={14} fill="currentColor" />
                          </button>
                        )}
                        {order.status === 'DELIVERED' && !returnActive && !order.review && (
                          <button
                            className="orders-fk-details-btn"
                            onClick={() => void requestReturn(order)}
                            disabled={returningOrderId === order.order_id}
                          >
                            {returningOrderId === order.order_id ? 'Submitting…' : 'Return order'}
                            <RotateCcw
                              size={14}
                              className={returningOrderId === order.order_id ? 'spin' : ''}
                            />
                          </button>
                        )}
                        <button
                          className="orders-fk-details-btn"
                          onClick={() => toggleOrder(order.order_id)}
                        >
                        {isOpen ? 'Hide details' : 'View details'}
                        {isOpen ? (
                          <ChevronUp size={16} />
                        ) : (
                          <ChevronDown size={16} />
                        )}
                      </button>
                      </div>
                    </div>

                    {isOpen && (
                      <div className="orders-fk-details">
                        <div className="orders-fk-details-grid">
                          <div>
                            <span>Delivery address</span>
                            <strong>{order.delivery_address}</strong>
                          </div>
                          <div>
                            <span>Current status</span>
                            <strong>
                              {effectiveStatus === 'RETURN_REQUESTED'
                                ? effectiveMeta.label
                                : meta.label}
                            </strong>
                          </div>
                          <div>
                            <span>Shop</span>
                            <strong>{order.shop_name || `Shop #${order.shop_id}`}</strong>
                          </div>
                          <div>
                            <span>Items</span>
                            <strong>{order.items.length}</strong>
                          </div>
                        </div>

                        {returnActive && (
                          <div className="orders-fk-return-state compact">
                            <div className="orders-fk-return-state-icon"><RotateCcw size={14} /></div>
                            <div>
                              <strong>{effectiveMeta.label}</strong>
                              <span>
                                {order.return_request?.reason || 'Return request submitted.'}
                              </span>
                            </div>
                            <span className="orders-fk-return-state-badge">
                              {String(order.return_request?.status || 'REQUESTED').replaceAll('_', ' ')}
                            </span>
                          </div>
                        )}

                        {deliveryLoadingId === order.order_id ? (
                          <div
                            style={{
                              marginBottom: 16,
                              padding: '12px 14px',
                              borderRadius: 14,
                              background: 'rgba(99,102,241,.06)',
                              border: '1px solid rgba(99,102,241,.12)',
                              color: '#64748b',
                              fontSize: 12,
                            }}
                          >
                            Loading delivery tracking…
                          </div>
                        ) : deliveryByOrder[order.order_id] ? (
                          <div
                            style={{
                              marginBottom: 16,
                              padding: '14px',
                              borderRadius: 16,
                              background: 'linear-gradient(135deg, rgba(37,99,235,.07), rgba(34,211,238,.05))',
                              border: '1px solid rgba(96,165,250,.18)',
                            }}
                          >
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                gap: 12,
                              }}
                            >
                              <div>
                                <div
                                  style={{
                                    fontSize: 10,
                                    fontWeight: 900,
                                    letterSpacing: '.11em',
                                    color: '#64748b',
                                  }}
                                >
                                  DELIVERY TRACKING
                                </div>
                                <div
                                  style={{
                                    marginTop: 4,
                                    fontWeight: 800,
                                    color: '#0f172a',
                                  }}
                                >
                                  {String(deliveryByOrder[order.order_id].status || 'NOT_ASSIGNED').replaceAll('_', ' ')}
                                </div>
                              </div>
                              <Truck size={20} color="#2563EB" />
                            </div>
                            {deliveryByOrder[order.order_id].driver_name && (
                              <div
                                style={{
                                  marginTop: 10,
                                  display: 'flex',
                                  gap: 14,
                                  flexWrap: 'wrap',
                                  fontSize: 11,
                                  color: '#475569',
                                }}
                              >
                                <span>
                                  Driver: <strong>{deliveryByOrder[order.order_id].driver_name}</strong>
                                </span>
                                {deliveryByOrder[order.order_id].driver_phone && (
                                  <span>
                                    {deliveryByOrder[order.order_id].driver_phone}
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        ) : null}

                        {order.status === 'DELIVERED' && order.review && (
                          <div className="orders-fk-review-card">
                            <div className="orders-fk-detail-eyebrow">YOUR VERIFIED REVIEW</div>
                            <div className="orders-fk-review-row">
                              <div className="orders-review-stars">
                                {Array.from({ length: 5 }, (_, index) => (
                                  <Star
                                    key={index}
                                    size={17}
                                    fill={index < Number(order.review?.rating || 0) ? 'currentColor' : 'none'}
                                  />
                                ))}
                              </div>
                              <span>{formatDate(order.review.created_at)}</span>
                            </div>
                            {order.review.comment && <p>“{order.review.comment}”</p>}
                          </div>
                        )}

                        {reviewingOrderId === order.order_id && !order.review && (
                          <div className="orders-fk-review-card editor">
                            <div className="orders-fk-detail-eyebrow">SHARE YOUR EXPERIENCE</div>
                            <h3>How was your order from {order.shop_name || 'the shop'}?</h3>
                            <div className="orders-review-stars">
                              {Array.from({ length: 5 }, (_, index) => {
                                const star = index + 1;
                                const active = star <= reviewRating;
                                return (
                                  <button
                                    key={star}
                                    type="button"
                                    className={active ? 'active' : ''}
                                    onClick={() => setReviewRating(star)}
                                    aria-label={'Rate ' + star}
                                  >
                                    <Star size={18} fill={active ? 'currentColor' : 'none'} />
                                  </button>
                                );
                              })}
                            </div>
                            <textarea
                              value={reviewComment}
                              onChange={(event) => setReviewComment(event.target.value)}
                              maxLength={500}
                              placeholder="Tell future shoppers what you liked about the shop, product quality or delivery."
                              rows={4}
                            />
                            <div className="orders-fk-review-actions">
                              <button
                                type="button"
                                className="orders-fk-details-btn"
                                onClick={() => setReviewingOrderId(null)}
                              >
                                Not now
                              </button>
                              <button
                                type="button"
                                className="orders-fk-primary-btn"
                                onClick={() => void submitReview(order)}
                              >
                                Publish review <Sparkles size={14} />
                              </button>
                            </div>
                          </div>
                        )}

                        <div className="orders-fk-items">
                          {order.items.map((item, idx) => {
                            const name =
                              item.product_name ||
                              item.name ||
                              'Product #' + item.product_id;
                            const unitPrice = Number(
                              item.unit_price ?? item.price ?? 0,
                            );
                            const lineTotal = Number(
                              item.line_total ?? unitPrice * item.quantity,
                            );

                            return (
                              <div
                                className="orders-fk-detail-item"
                                key={item.product_id + '-' + idx}
                              >
                                <div className="orders-fk-product-icon small">
                                  <Package size={18} />
                                </div>
                                <div className="orders-fk-detail-name">
                                  <strong>{name}</strong>
                                  <span>
                                    Qty {item.quantity} ·{' '}
                                    {formatCurrency(unitPrice)} each
                                  </span>
                                </div>
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
