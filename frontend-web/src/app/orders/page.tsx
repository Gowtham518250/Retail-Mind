'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import { motion, useReducedMotion } from 'framer-motion';
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
import styles from './orders.module.css';

const OrderPackageScene = dynamic(
  () => import('../../components/OrderPackageScene'),
  { ssr: false },
);

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
  payment_method?: string;
  payment_status?: string;
  payment_reference?: string | null;
  total_amount: number;
  delivery_address: string;
  items: OrderItem[];
  created_at: string;
  review?: OrderReview | null;
  can_cancel?: boolean;
  return_request?: ReturnRequest | null;
}

function readOrderDeliveryDetails(value: string) {
  const raw = String(value || '');
  const phone = raw.match(/(?:^|\s\|\s)Contact phone:\s*(\d{10})/i)?.[1] || '';
  const orderNotes = raw.match(/(?:^|\s\|\s)Order notes:\s*([\s\S]*)$/i)?.[1]?.trim() || '';
  const address = raw
    .replace(/\s*\|\s*Contact phone:\s*\d{10}/i, '')
    .replace(/\s*\|\s*Order notes:[\s\S]*$/i, '')
    .trim();
  return { address, phone, orderNotes };
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
type OrderFilter =
  | 'ALL'
  | 'PENDING'
  | 'ACCEPTED'
  | 'DISPATCHED'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'REJECTED'
  | 'RETURNS';

const ORDER_FILTERS: { value: OrderFilter; label: string }[] = [
  { value: 'ALL', label: 'All orders' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'ACCEPTED', label: 'Confirmed' },
  { value: 'DISPATCHED', label: 'Dispatched' },
  { value: 'DELIVERED', label: 'Delivered' },
  { value: 'CANCELLED', label: 'Cancelled' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'RETURNS', label: 'Returns' },
];

function getCustomerSyncCursorKey(token: string): string | null {
  try {
    // The JWT subject is used only to namespace local cursor storage. The API
    // still authenticates and authorizes every change-feed request.
    const encodedPayload = token.split('.')[1];
    if (!encodedPayload) return null;
    const base64 = encodedPayload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, '=');
    const claims = JSON.parse(window.atob(padded));
    const subject = String(claims?.sub || '').trim();
    return subject ? 'retailmind.customer-order-sync.v1.' + subject : null;
  } catch {
    return null;
  }
}

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
  const [notice, setNotice] = useState('');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [liveConnected, setLiveConnected] = useState(false);
  const [filter, setFilter] = useState<OrderFilter>('ALL');
  const [query, setQuery] = useState('');
  const [expandedOrders, setExpandedOrders] = useState<Set<number>>(new Set());
  const [returningOrderId, setReturningOrderId] = useState<number | null>(null);
  const [cancelingOrderId, setCancelingOrderId] = useState<number | null>(null);
  const [reviewingOrderId, setReviewingOrderId] = useState<number | null>(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const [deliveryByOrder, setDeliveryByOrder] = useState<Record<number, any>>({});
  const [deliveryLoadingId, setDeliveryLoadingId] = useState<number | null>(null);
  const customerCursorKeyRef = useRef<string | null>(null);
  const customerFeedSupportedRef = useRef<boolean | null>(null);
  const customerFeedProbeAfterRef = useRef(0);
  const customerFeedPollInProgressRef = useRef(false);
  const seenRealtimeEventIdsRef = useRef<Set<string>>(new Set());
  const ordersFetchRequestIdRef = useRef(0);
  const router = useRouter();
  const shouldReduceMotion = useReducedMotion();

  const fetchOrders = useCallback(
    async (silent = false): Promise<boolean> => {
      const requestId = ++ordersFetchRequestIdRef.current;
      const token = localStorage.getItem('customerToken');

      if (!token) {
        router.push('/auth');
        return false;
      }

      if (silent) setRefreshing(true);

      try {
        const response = await fetch(API_BASE + '/store/my-orders', {
          headers: { Authorization: 'Bearer ' + token },
          cache: 'no-store',
        });

        if (requestId !== ordersFetchRequestIdRef.current) return false;

        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return false;
          }
          throw new Error('Unable to load your orders right now.');
        }

        const data = await response.json();
        if (requestId !== ordersFetchRequestIdRef.current) return false;
        setOrders(Array.isArray(data.orders) ? data.orders : []);
        setError('');
        setLastUpdated(new Date());
        return true;
      } catch (err: any) {
        if (requestId === ordersFetchRequestIdRef.current) {
          setError(err?.message || 'Unable to refresh orders right now.');
        }
        return false;
      } finally {
        if (requestId === ordersFetchRequestIdRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [router],
  );

  useEffect(() => {
    let stopped = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let reconnectDelayMs = 1000;

    const markRealtimeEventSeen = (eventId: unknown) => {
      const id = String(eventId || '').trim();
      if (!id) return;
      const seen = seenRealtimeEventIdsRef.current;
      seen.add(id);
      if (seen.size > 500) {
        const oldest = seen.values().next().value;
        if (oldest) seen.delete(oldest);
      }
    };

    const initializeCustomerCursor = async (
      token: string,
      forceBaseline = false,
    ): Promise<boolean> => {
      const cursorKey = getCustomerSyncCursorKey(token);
      if (!cursorKey) return false;
      customerCursorKeyRef.current = cursorKey;

      const saved = localStorage.getItem(cursorKey);
      const savedCursor = saved === null ? Number.NaN : Number(saved);
      const savedIsValid =
        Number.isSafeInteger(savedCursor) && savedCursor >= 0;
      if (!forceBaseline && savedIsValid) {
        customerFeedSupportedRef.current = true;
        return true;
      }

      if (Date.now() < customerFeedProbeAfterRef.current) return false;

      try {
        const response = await fetch(
          API_BASE + '/api/sync/my-changes?after=0&limit=1',
          {
            headers: { Authorization: 'Bearer ' + token },
            cache: 'no-store',
          },
        );

        if (response.status === 404) {
          // Older Render deployments can serve this frontend before the new
          // backend is active. Back off and retain the five-minute REST safety net.
          customerFeedSupportedRef.current = false;
          customerFeedProbeAfterRef.current = Date.now() + 5 * 60 * 1000;
          return false;
        }
        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem('customerToken');
          router.push('/auth');
          return false;
        }
        if (!response.ok) {
          customerFeedProbeAfterRef.current = Date.now() + 60 * 1000;
          return false;
        }

        const data = await response.json();
        const highWatermark = Number(data?.high_watermark ?? 0);
        if (!Number.isSafeInteger(highWatermark) || highWatermark < 0) {
          throw new Error('Invalid customer sync baseline.');
        }

        if (forceBaseline || !savedIsValid) {
          // Establish a high-water mark before the initial order snapshot.
          // The catch-up immediately after fetchOrders covers writes that land
          // while the snapshot is being read.
          localStorage.setItem(cursorKey, String(highWatermark));
        }
        customerFeedSupportedRef.current = true;
        customerFeedProbeAfterRef.current = 0;
        return true;
      } catch {
        customerFeedProbeAfterRef.current = Date.now() + 60 * 1000;
        return false;
      }
    };

    const pollCustomerChanges = async (): Promise<void> => {
      if (stopped || customerFeedPollInProgressRef.current) return;
      customerFeedPollInProgressRef.current = true;

      try {
        const token = localStorage.getItem('customerToken');
        if (!token) {
          router.push('/auth');
          return;
        }

        if (customerFeedSupportedRef.current !== true) {
          const initialized = await initializeCustomerCursor(token);
          if (!initialized) return;
        }

        const cursorKey = customerCursorKeyRef.current;
        if (!cursorKey) return;

        let cursor = Number(localStorage.getItem(cursorKey) ?? 0);
        if (!Number.isSafeInteger(cursor) || cursor < 0) cursor = 0;
        let nextCursor = cursor;
        let hasMore = true;
        let pageCount = 0;
        let requiresOrderRefresh = false;

        // Keep each wake-up bounded for mobile connections and low-memory tabs.
        while (hasMore && pageCount < 3) {
          const response = await fetch(
            API_BASE +
              '/api/sync/my-changes?after=' +
              cursor +
              '&limit=250',
            {
              headers: { Authorization: 'Bearer ' + token },
              cache: 'no-store',
            },
          );

          if (response.status === 404) {
            customerFeedSupportedRef.current = false;
            customerFeedProbeAfterRef.current = Date.now() + 5 * 60 * 1000;
            return;
          }
          if (response.status === 409) {
            localStorage.removeItem(cursorKey);
            const rebased = await initializeCustomerCursor(token, true);
            if (rebased) {
              // Reconcile the full order snapshot after a cursor reset. Any
              // event committed while reading that snapshot stays above the
              // new baseline and will be picked up by the next poll.
              await fetchOrders(true);
            }
            return;
          }
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return;
          }
          if (!response.ok) {
            throw new Error('Customer change feed returned ' + response.status);
          }

          const data = await response.json();
          const events = Array.isArray(data?.events) ? data.events : [];
          for (const event of events) {
            const type = String(event?.type || '');
            const eventId = String(event?.event_id || '');
            const alreadyAppliedByRealtime =
              eventId !== '' && seenRealtimeEventIdsRef.current.has(eventId);
            if (
              !alreadyAppliedByRealtime &&
              (type === 'order.created' || type === 'order.status_changed' || type === 'order.payment_confirmed')
            ) {
              requiresOrderRefresh = true;
            }
          }

          const candidateCursor = Number(data?.next_cursor);
          if (!Number.isSafeInteger(candidateCursor) || candidateCursor < cursor) {
            throw new Error('Invalid customer sync cursor.');
          }
          nextCursor = candidateCursor;
          cursor = candidateCursor;
          hasMore = data?.has_more === true;
          pageCount += 1;
        }

        // A failed snapshot must never advance the cursor. The same durable
        // events are retried on the next wake-up instead of being skipped.
        if (requiresOrderRefresh) {
          const refreshed = await fetchOrders(true);
          if (!refreshed) return;
        }

        localStorage.setItem(cursorKey, String(nextCursor));
        customerFeedSupportedRef.current = true;
      } catch {
        // Keep the existing cursor. A later poll retries the same durable page.
        if (customerFeedSupportedRef.current !== true) {
          customerFeedProbeAfterRef.current = Date.now() + 60 * 1000;
        }
      } finally {
        customerFeedPollInProgressRef.current = false;
      }
    };

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
          // Recover any event that was committed while the socket was down.
          void pollCustomerChanges();
        };

        socket.onmessage = async (message) => {
          try {
            const event = JSON.parse(message.data);
            const eventId = String(event?.event_id || '');

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
              markRealtimeEventSeen(eventId);
            } else if (event?.type === 'order.payment_confirmed') {
              const orderId = Number(event.order_id);
              setOrders((current) =>
                current.map((order) =>
                  order.order_id === orderId
                    ? {
                        ...order,
                        payment_method: 'UPI',
                        payment_status: 'PAID',
                        payment_reference: event.payment_reference || order.payment_reference,
                      }
                    : order,
                ),
              );
              setError('');
              setLastUpdated(new Date());
              markRealtimeEventSeen(eventId);
            } else if (event?.type === 'order.created') {
              const refreshed = await fetchOrders(true);
              if (refreshed) markRealtimeEventSeen(eventId);
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

    const bootstrap = async () => {
      const token = localStorage.getItem('customerToken');
      if (!token) {
        router.push('/auth');
        return;
      }

      // Establish the baseline before fetching the snapshot; changes that land
      // during the snapshot remain above the cursor and will be caught up next.
      await initializeCustomerCursor(token);
      await fetchOrders();
      if (customerFeedSupportedRef.current === true) {
        await pollCustomerChanges();
      }
      void connectRealtime();
    };

    void bootstrap();

    const feedInterval = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void pollCustomerChanges();
      }
    }, 30000);

    // The five-minute full snapshot is the conservative fallback for an
    // unavailable endpoint or any write path that has not yet emitted an event.
    const safetyInterval = window.setInterval(async () => {
      if (document.visibilityState !== 'visible') return;
      const token = localStorage.getItem('customerToken');
      if (token && customerFeedSupportedRef.current !== true) {
        await initializeCustomerCursor(token);
      }
      void fetchOrders(true);
    }, 5 * 60 * 1000);

    const onVisible = () => {
      if (document.visibilityState === 'visible') {
        if (customerFeedSupportedRef.current === true) {
          void pollCustomerChanges();
        } else {
          void fetchOrders(true);
        }
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

      window.clearInterval(feedInterval);
      window.clearInterval(safetyInterval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [fetchOrders, router]);

  const activeCount = useMemo(
    () => orders.filter((order) => !TERMINAL_STATUSES.includes(order.status)).length,
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

  const visibleOrders = useMemo(() => {
    const q = query.trim().toLowerCase();

    return orders.filter((order) => {
      const filterMatch =
        filter === 'ALL' ||
        (filter === 'RETURNS' &&
          (order.status === 'RETURNED' || activeReturnRequest(order))) ||
        (filter === 'CANCELLED' && order.status === 'CANCELLED') ||
        (filter === 'REJECTED' && order.status === 'REJECTED') ||
        order.status === filter;

      const queryMatch =
        !q ||
        String(order.order_id).includes(q) ||
        String(order.shop_name || '').toLowerCase().includes(q) ||
        (STATUS_META[order.status]?.label || order.status).toLowerCase().includes(q) ||
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
        '? Orders can only be cancelled before dispatch. Reserved stock will be released, and any paid online amount may require a refund.',
    );
    if (!confirmed) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    setError('');
    setNotice('');
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

      if (data?.success !== true || data?.status !== 'CANCELLED') {
        throw new Error('The server did not confirm the order cancellation.');
      }

      setNotice(data.message || 'Order #' + order.order_id + ' was cancelled successfully.');
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

      setNotice(
        'Return request submitted for Order #' +
          order.order_id +
          '. The shop will review it.',
      );
      await fetchOrders(true);
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

      setNotice('Thanks! Your verified review is now visible on the shop.');
      setReviewingOrderId(null);
      setReviewComment('');
      setReviewRating(5);
      await fetchOrders(true);
    } catch (err: any) {
      setError(err?.message || 'Unable to save your review.');
    }
  };



  return (
    <div className={`${styles.page} orders-fk-page`} data-experience="orders">
      <div className="orders-fk-shell">
        <header className="orders-fk-topbar">
        <div className="orders-fk-scene-wrap" aria-hidden="true">
          <OrderPackageScene />
        </div>
        <div className="orders-fk-brand">
            <button
              className="orders-fk-back"
              onClick={() => {
                const referrer = document.referrer;
                const cameFromThisSite =
                  referrer === window.location.origin ||
                  referrer.startsWith(window.location.origin + '/');
                if (cameFromThisSite && window.history.length > 1) router.back();
                else router.push('/');
              }}
              type="button"
              aria-label="Go back"
            >
              <ArrowLeft size={18} />
            </button>
            <div className="orders-fk-brand-copy">
              <span className="orders-fk-eyebrow">ORDER HISTORY</span>
              <h1 className="orders-fk-brand-title">Your Orders</h1>
              <p className="orders-fk-brand-subtitle">
                Every order, every update, all in one place.
              </p>
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

        <section className="orders-fk-stats" aria-label="Order summary">
          {[
            { label: 'Total orders', value: orders.length, Icon: Package },
            { label: 'In progress', value: activeCount, Icon: Clock },
            { label: 'Delivered', value: deliveredCount, Icon: CheckCircle2 },
            { label: 'Cancelled or rejected', value: cancelledCount, Icon: Ban },
          ].map(({ label, value, Icon }) => (
            <div className="orders-fk-stat" key={label}>
              <span className="orders-fk-stat-icon" aria-hidden="true">
                <Icon size={17} />
              </span>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </section>

        <section className="orders-fk-toolbar">
          <div
            className="orders-fk-tabs"
            role="group"
            aria-label="Filter orders by status"
          >
            {ORDER_FILTERS.map(({ value, label }) => (
              <button
                type="button"
                key={value}
                className={
                  'orders-fk-tab ' + (filter === value ? 'active' : '')
                }
                aria-pressed={filter === value}
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

        {notice && (
          <div className="orders-fk-notice" role="status">
            <CheckCircle2 size={16} aria-hidden="true" />
            {notice}
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
            <h2>
              {orders.length === 0
                ? 'No orders yet'
                : query
                  ? 'No orders match your search'
                  : filter === 'ALL'
                    ? 'No matching orders'
                    : 'No orders in this status'}
            </h2>
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
            {orders.length > 0 && (
              <button
                type="button"
                className="orders-fk-primary-btn"
                onClick={() => {
                  setFilter('ALL');
                  setQuery('');
                }}
              >
                Clear filters
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
                const deliveryDetails = readOrderDeliveryDetails(order.delivery_address);
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
                    initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{
                      duration: shouldReduceMotion ? 0 : 0.3,
                      delay: shouldReduceMotion ? 0 : Math.min(orderIndex * 0.04, 0.2),
                    }}
                    className="orders-fk-card"
                  >
                    <div className="orders-fk-card-top">
                      <div>
                        <div className="orders-fk-order-number">
                          Order #{order.order_id}
                        </div>
                        <div className="orders-fk-shop-name">
                          {order.shop_name || `Shop #${order.shop_id}`}
                        </div>
                        <div className="orders-fk-order-date">
                          {formatDate(order.created_at)}
                        </div>
                      </div>
                      <div className="orders-fk-card-total">
                        <span>Order total</span>
                        <strong>{formatCurrency(order.total_amount)}</strong>
                        <span className="orders-fk-payment-state">
                          {(() => {
                            const paymentStatus = String(order.payment_status || '').toUpperCase();
                            const paymentMethod = String(order.payment_method || '').toUpperCase();
                            if (paymentStatus === 'REFUND_REQUIRED') return 'Refund required';
                            if (paymentStatus === 'REVIEW_REQUIRED') return 'Payment needs review';
                            if (paymentStatus === 'PAID') return paymentMethod === 'UPI' ? 'UPI payment confirmed' : 'Paid';
                            if (paymentStatus === 'PENDING') return 'UPI payment pending';
                            if (paymentStatus === 'COD_DUE') return 'Cash on delivery';
                            if (paymentStatus === 'UNPAID') return 'Payment due';
                            return '';
                          })()}
                        </span>
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
                          effectiveStatus.toLowerCase()
                        }
                      >
                        <Icon size={14} /> {effectiveMeta.label}
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
                        <span>{deliveryDetails.address || order.delivery_address}</span>
                      </div>
                      <div className="orders-fk-details-actions">
                        {(order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status)) && (
                          <button
                            className="orders-fk-details-btn danger"
                            onClick={() => void cancelOrder(order)}
                            disabled={cancelingOrderId !== null}
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
                          type="button"
                          className="orders-fk-details-btn"
                          onClick={() => toggleOrder(order.order_id)}
                          aria-expanded={isOpen}
                          aria-controls={`order-details-${order.order_id}`}
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
                      <div
                        className="orders-fk-details"
                        id={`order-details-${order.order_id}`}
                      >
                        <div className="orders-fk-details-grid">
                          <div>
                            <span>Delivery address</span>
                            <strong>{deliveryDetails.address || order.delivery_address}</strong>
                          </div>
                          <div>
                            <span>Contact phone</span>
                            <strong>{deliveryDetails.phone || 'Not provided for this order'}</strong>
                          </div>
                          {deliveryDetails.orderNotes && (
                            <div>
                              <span>Order instructions</span>
                              <strong>{deliveryDetails.orderNotes}</strong>
                            </div>
                          )}
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
