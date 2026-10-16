'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
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
  Store,
  X,
  AlertCircle,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';

interface OrderItem {
  product_id: number;
  product_name?: string;
  name?: string;
  image_url?: string | null;
  product_image_url?: string | null;
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
  subtotal?: number;
  online_setup_fee?: number;
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

type OrderFilter = 'ALL' | 'PENDING' | 'ACCEPTED' | 'DISPATCHED' | 'DELIVERED' | 'CANCELLED' | 'RETURNED' | 'REJECTED';

const ORDER_FILTERS: { value: OrderFilter; label: string }[] = [
  { value: 'ALL', label: 'All orders' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'ACCEPTED', label: 'Accepted' },
  { value: 'DISPATCHED', label: 'Dispatched' },
  { value: 'DELIVERED', label: 'Delivered' },
  { value: 'CANCELLED', label: 'Cancelled' },
  { value: 'RETURNED', label: 'Returned' },
  { value: 'REJECTED', label: 'Rejected' },
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
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(date);
}

function resolveOrderImage(value?: string | null) {
  if (!value) return '';
  if (/^https?:\/\//i.test(value)) return value;
  return API_BASE + (value.startsWith('/') ? value : '/' + value);
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
  const normalized = String(status || '').toUpperCase();
  const current = statusIndex(normalized);
  const terminal = !STATUS_STEPS.includes(normalized as (typeof STATUS_STEPS)[number]);

  if (terminal) {
    const meta = STATUS_META[normalized];
    const Icon = meta?.icon || CircleDot;
    return (
      <div className={'rejected-banner ' + normalized.toLowerCase()} role="status">
        <Icon size={18} aria-hidden="true" />
        <div>
          <strong>{meta?.label || 'Status update'}</strong>
          <span>{meta?.description || 'The shop has updated this order.'}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="order-timeline" role="list" aria-label="Order progress">
      {STATUS_STEPS.map((step, index) => {
        const meta = STATUS_META[step];
        const Icon = meta.icon;
        const completed = current >= index;
        const active = current === index;
        return (
          <div
            className={'timeline-step ' + (completed ? 'complete ' : '') + (active ? 'active' : '')}
            key={step}
            role="listitem"
            aria-current={active ? 'step' : undefined}
          >
            <div
              className={'timeline-node ' + (completed ? 'completed ' : '') + (active ? 'active' : '')}
              style={completed ? { borderColor: meta.tone, color: meta.tone } : undefined}
              aria-hidden="true"
            >
              {completed ? <Icon size={15} /> : <CircleDot size={12} />}
            </div>
            <div className="timeline-copy">
              <div className="timeline-label">{meta.label}</div>
              {active && <div className="timeline-description">{meta.description}</div>}
            </div>
            {index < STATUS_STEPS.length - 1 && (
              <div className={'timeline-line ' + (current > index ? 'filled' : '')} aria-hidden="true" />
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
  const [periodFilter, setPeriodFilter] = useState<'ALL' | '30D' | '90D'>('ALL');
  const [expandedOrders, setExpandedOrders] = useState<Set<number>>(new Set());
  const [trackingOrders, setTrackingOrders] = useState<Set<number>>(new Set());
  const [returningOrderId, setReturningOrderId] = useState<number | null>(null);
  const [cancelingOrderId, setCancelingOrderId] = useState<number | null>(null);
  const [cancelCandidate, setCancelCandidate] = useState<Order | null>(null);
  const [cancelDialogError, setCancelDialogError] = useState('');
  const cancelConfirmButtonRef = useRef<HTMLButtonElement | null>(null);
  const cancelDialogRef = useRef<HTMLElement | null>(null);
  const cancelTriggerRef = useRef<HTMLButtonElement | null>(null);
  const ordersRequestIdRef = useRef(0);
  const ordersRevisionRef = useRef(0);
  const [reviewingOrderId, setReviewingOrderId] = useState<number | null>(null);
  const [reviewSubmittingId, setReviewSubmittingId] = useState<number | null>(null);
  const [reviewRating, setReviewRating] = useState(5);
  const [reviewComment, setReviewComment] = useState('');
  const customerCursorKeyRef = useRef<string | null>(null);
  const customerFeedSupportedRef = useRef<boolean | null>(null);
  const customerFeedProbeAfterRef = useRef(0);
  const customerFeedPollInProgressRef = useRef(false);
  const seenRealtimeEventIdsRef = useRef<Set<string>>(new Set());
  const router = useRouter();

  useEffect(() => {
    if (!cancelCandidate) {
      if (cancelTriggerRef.current?.isConnected) cancelTriggerRef.current.focus();
      cancelTriggerRef.current = null;
      return;
    }

    cancelConfirmButtonRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && cancelingOrderId === null) {
        setCancelCandidate(null);
        setCancelDialogError('');
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = cancelDialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [cancelCandidate, cancelingOrderId]);

  const fetchOrders = useCallback(
    async (silent = false): Promise<boolean> => {
      const token = localStorage.getItem('customerToken');
      if (!token) {
        setLoading(false);
        router.push('/auth');
        return false;
      }

      const requestId = ++ordersRequestIdRef.current;
      const revisionAtStart = ordersRevisionRef.current;
      if (silent) setRefreshing(true);
      else setLoading(true);

      try {
        const response = await fetch(API_BASE + '/store/my-orders', {
          headers: { Authorization: 'Bearer ' + token },
          cache: 'no-store',
        });

        if (requestId !== ordersRequestIdRef.current) return false;
        if (!response.ok) {
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            router.push('/auth');
            return false;
          }
          throw new Error('Unable to load your orders right now.');
        }

        const data = await response.json();
        if (requestId !== ordersRequestIdRef.current || revisionAtStart !== ordersRevisionRef.current) {
          return false;
        }

        setOrders(Array.isArray(data.orders) ? data.orders : []);
        setError('');
        setLastUpdated(new Date());
        return true;
      } catch (err: unknown) {
        if (requestId === ordersRequestIdRef.current && revisionAtStart === ordersRevisionRef.current) {
          setError(err instanceof Error ? err.message : 'Unable to refresh orders right now.');
        }
        return false;
      } finally {
        if (requestId === ordersRequestIdRef.current) {
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
          ordersRevisionRef.current += 1;
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
              ordersRevisionRef.current += 1;
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
              ordersRevisionRef.current += 1;
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
              ordersRevisionRef.current += 1;
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
    () => orders.filter((order) => ['PENDING', 'ACCEPTED', 'DISPATCHED'].includes(order.status)).length,
    [orders],
  );

  const cancelledCount = useMemo(
    () => orders.filter((order) => order.status === 'CANCELLED').length,
    [orders],
  );

  const deliveredCount = useMemo(
    () => orders.filter((order) => order.status === 'DELIVERED').length,
    [orders],
  );

  const visibleOrders = useMemo(() => {
    const q = query.trim().toLowerCase();
    const now = Date.now();
    const periodMs = periodFilter === '30D'
      ? 30 * 24 * 60 * 60 * 1000
      : periodFilter === '90D'
        ? 90 * 24 * 60 * 60 * 1000
        : null;

    return orders.filter((order) => {
      const filterMatch = filter === 'ALL' || order.status === filter;
      const queryMatch =
        !q ||
        String(order.order_id).includes(q) ||
        String(order.shop_name || '').toLowerCase().includes(q) ||
        String(order.delivery_address || '').toLowerCase().includes(q) ||
        order.items.some((item) =>
          String(item.product_name || item.name || '').toLowerCase().includes(q),
        );

      const createdAt = new Date(order.created_at).getTime();
      const dateMatch = !periodMs ||
        (Number.isFinite(createdAt) && now - createdAt >= 0 && now - createdAt <= periodMs);
      return filterMatch && queryMatch && dateMatch;
    });
  }, [orders, filter, query, periodFilter]);

  const clearOrderFilters = () => {
    setFilter('ALL');
    setQuery('');
    setPeriodFilter('ALL');
  };

  const toggleTracking = (orderId: number) => {
    setTrackingOrders((current) => {
      const next = new Set(current);
      if (next.has(orderId)) next.delete(orderId);
      else next.add(orderId);
      return next;
    });
  };

  const toggleOrder = (orderId: number) => {
    setExpandedOrders((current) => {
      const next = new Set(current);
      if (next.has(orderId)) next.delete(orderId);
      else next.add(orderId);
      return next;
    });
  };

  const requestCancelOrder = (order: Order, trigger?: HTMLButtonElement) => {
    const canCancel = order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status);
    if (!canCancel || cancelingOrderId !== null) return;
    cancelTriggerRef.current = trigger || null;
    setCancelDialogError('');
    setCancelCandidate(order);
  };

  const confirmCancelOrder = async () => {
    const order = cancelCandidate;
    if (!order || cancelingOrderId !== null) return;

    const canCancel = order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status);
    if (!canCancel) {
      setCancelDialogError('This order is no longer eligible for cancellation. Refresh your order history.');
      return;
    }

    const token = localStorage.getItem('customerToken');
    if (!token) {
      setCancelCandidate(null);
      router.push('/auth');
      return;
    }

    setCancelingOrderId(order.order_id);
    setCancelDialogError('');
    try {
      const response = await fetch(API_BASE + '/store/order/' + order.order_id + '/cancel', {
        method: 'POST',
        headers: { Authorization: 'Bearer ' + token },
        cache: 'no-store',
      });
      const data = await response.json().catch(() => ({}));

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('customerToken');
        setCancelCandidate(null);
        router.push('/auth');
        return;
      }
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to cancel this order.');
      }

      const serverStatus = String(data?.status || '').toUpperCase();
      if (serverStatus !== 'CANCELLED') {
        throw new Error('The server did not confirm cancellation. Refresh your order history before retrying.');
      }

      ordersRevisionRef.current += 1;
      setOrders((current) =>
        current.map((existing) =>
          existing.order_id === order.order_id
            ? {
                ...existing,
                status: serverStatus,
                can_cancel: false,
                payment_status: data?.payment_status || existing.payment_status,
              }
            : existing,
        ),
      );
      setNotice(data?.message || ('Cancellation confirmed for Order #' + order.order_id + '.'));
      setError('');
      setCancelCandidate(null);
      await fetchOrders(true);
    } catch (err: unknown) {
      setCancelDialogError(err instanceof Error ? err.message : 'Unable to cancel this order.');
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

      ordersRevisionRef.current += 1;
      setNotice('Return request submitted for Order #' + order.order_id + '. The shop will review it.');
      setError('');
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

    setReviewSubmittingId(order.order_id);
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

      ordersRevisionRef.current += 1;
      setNotice('Thanks! Your verified review is now visible on the shop.');
      setError('');
      setReviewingOrderId(null);
      setReviewComment('');
      setReviewRating(5);
      await fetchOrders(true);
    } catch (err: any) {
      setError(err?.message || 'Unable to save your review.');
    } finally {
      setReviewSubmittingId(null);
    }
  };



  return (
    <div className="orders-fk-page">
      <div className="orders-fk-shell">
        <header className="orders-fk-topbar">
          <div className="orders-fk-header-row">
            <div className="orders-fk-brand">
              <button
                className="orders-fk-back"
                type="button"
                onClick={() => router.push('/')}
                aria-label="Back to shopping"
                title="Back to shopping"
              >
                <ArrowLeft size={18} />
              </button>
              <div className="orders-fk-heading">
                <div className="orders-fk-eyebrow">RETAIL MIND / CUSTOMER ACCOUNT</div>
                <h1 className="orders-fk-brand-title">Your Orders</h1>
                <p className="orders-fk-brand-subtitle">Every order, every update, all in one place.</p>
              </div>
            </div>
            <div className={'orders-fk-live ' + (liveConnected ? 'connected' : 'offline')} role="status" aria-live="polite">
              <span className={'orders-fk-live-dot' + (liveConnected ? '' : ' offline')} aria-hidden="true" />
              <span>{liveConnected ? 'Live updates connected' : 'Reconnecting to live updates'}</span>
            </div>
          </div>

          <div className="orders-fk-top-actions">
            <label className="orders-fk-search">
              <Search size={17} aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search order, shop or product"
                aria-label="Search orders by number, shop, product or delivery address"
              />
            </label>
            <label className="orders-fk-period">
              <span className="sr-only">Filter orders by date</span>
              <select
                value={periodFilter}
                onChange={(event) => setPeriodFilter(event.target.value as 'ALL' | '30D' | '90D')}
                aria-label="Filter orders by date"
              >
                <option value="ALL">All time</option>
                <option value="30D">Last 30 days</option>
                <option value="90D">Last 90 days</option>
              </select>
              <ChevronDown size={14} aria-hidden="true" />
            </label>
            <button
              className="orders-fk-refresh"
              type="button"
              onClick={() => void fetchOrders(true)}
              disabled={refreshing}
              title={liveConnected ? 'Live updates connected. Refresh orders' : 'Refresh orders'}
              aria-label="Refresh orders"
            >
              <RefreshCw size={15} className={refreshing ? 'spin' : ''} aria-hidden="true" />
            </button>
          </div>
        </header>

        {notice && (
          <div className="orders-fk-notice" role="status" aria-live="polite">
            <CheckCircle2 size={17} aria-hidden="true" />
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice('')} aria-label="Dismiss message"><X size={16} /></button>
          </div>
        )}

        {loading ? (
          <section className="orders-fk-stats orders-fk-stats-loading" aria-label="Loading order summary" aria-busy="true">
            {Array.from({ length: 4 }, (_, index) => (
              <div className="orders-fk-stat-skeleton" key={index}><span /><strong /></div>
            ))}
          </section>
        ) : error && orders.length === 0 ? null : (
          <section className="orders-fk-stats" aria-label="Order summary">
            <div className="orders-fk-stat">
              <div className="orders-fk-stat-heading"><span className="orders-fk-stat-icon"><ShoppingBag size={17} /></span><span>Total orders</span></div>
              <strong>{orders.length}</strong>
              <small>All time</small>
            </div>
            <div className="orders-fk-stat">
              <div className="orders-fk-stat-heading"><span className="orders-fk-stat-icon in-progress"><Clock size={17} /></span><span>In progress</span></div>
              <strong>{activeCount}</strong>
              <small>Pending, accepted or dispatched</small>
            </div>
            <div className="orders-fk-stat">
              <div className="orders-fk-stat-heading"><span className="orders-fk-stat-icon delivered"><CheckCircle2 size={17} /></span><span>Delivered</span></div>
              <strong>{deliveredCount}</strong>
              <small>Delivered orders</small>
            </div>
            <div className="orders-fk-stat">
              <div className="orders-fk-stat-heading"><span className="orders-fk-stat-icon cancelled"><Ban size={17} /></span><span>Cancelled</span></div>
              <strong>{cancelledCount}</strong>
              <small>Cancellation confirmed by the server</small>
            </div>
          </section>
        )}

        <section className="orders-fk-history" aria-label="Order history">
          <div className="orders-fk-history-heading">
            <div>
              <span className="orders-fk-eyebrow">ORDER HISTORY</span>
              <h2>Everything in one place.</h2>
              <p>Choose a status or search the details of an order from your account.</p>
            </div>
            <span className="orders-fk-result-count">{visibleOrders.length} of {orders.length} orders</span>
          </div>
          <div className="orders-fk-toolbar">
            <div className="orders-fk-tabs" role="group" aria-label="Filter orders by status">
              {ORDER_FILTERS.map(({ value, label }) => {
                const count = value === 'ALL'
                  ? orders.length
                  : orders.filter((order) => order.status === value).length;
                return (
                  <button
                    key={value}
                    type="button"
                    className={'orders-fk-tab ' + (filter === value ? 'active' : '')}
                    onClick={() => setFilter(value)}
                    aria-pressed={filter === value}
                  >
                    <span>{label}</span>
                    <span className="orders-fk-tab-count">{count}</span>
                  </button>
                );
              })}
            </div>
          </div>
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
          <div className="orders-fk-empty" role="status">
            <div className="orders-fk-empty-illustration">
              <ShoppingBag size={29} aria-hidden="true" />
            </div>
            <span className="orders-fk-eyebrow">{orders.length === 0 ? 'A FRESH START' : 'NO MATCHES'}</span>
            <h2>{orders.length === 0 ? 'Your next favourite is out there.' : 'No orders match these filters.'}</h2>
            <p>
              {orders.length === 0
                ? 'When you place an order from a Retail Mind shop, its status and details will appear here.'
                : 'Clear the status, search or date filters to see your other orders.'}
            </p>
            {orders.length === 0 ? (
              <button type="button" className="orders-fk-primary-btn" onClick={() => router.push('/')}>
                Browse shops <ArrowLeft size={15} className="orders-fk-arrow-forward" />
              </button>
            ) : (
              <button type="button" className="orders-fk-primary-btn" onClick={clearOrderFilters}>
                Clear filters <X size={15} />
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
                      <div className="orders-fk-order-identity">
                        <button
                          type="button"
                          className="orders-fk-order-number-trigger"
                          onClick={() => toggleOrder(order.order_id)}
                          aria-expanded={isOpen}
                          aria-controls={'order-details-' + order.order_id}
                        >
                          <span className="orders-fk-order-number">Order #{order.order_id}</span>
                          {isOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                        </button>
                        <div className="orders-fk-order-date">{formatDate(order.created_at)}</div>
                        <div className="orders-fk-shop-name"><Store size={14} aria-hidden="true" /> {order.shop_name || 'Local shop'}</div>
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
                        {resolveOrderImage(firstItem?.image_url || firstItem?.product_image_url) ? (
                          <img
                            src={resolveOrderImage(firstItem?.image_url || firstItem?.product_image_url)}
                            alt=""
                            loading="lazy"
                          />
                        ) : (
                          <Package size={24} />
                        )}
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
) : trackingOrders.has(order.order_id) ? (
  <div className="orders-fk-tracking-panel">
    <div className="orders-fk-tracking-heading">
      <div><span>ORDER TRACKING</span><strong>#{order.order_id}</strong></div>
      <span className="orders-fk-tracking-current">{effectiveMeta.label}</span>
    </div>
    <OrderTimeline status={order.status} />
  </div>
) : null}

                    <div className="orders-fk-card-actions">
                      <div className="orders-fk-delivery">
                        <MapPin size={16} />
                        <span>{order.delivery_address}</span>
                      </div>
                      <div className="orders-fk-details-actions">
                        {(order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status)) && (
                          <button
                            className="orders-fk-details-btn danger"
                            type="button"
                            onClick={(event) => requestCancelOrder(order, event.currentTarget)}
                            disabled={cancelingOrderId !== null || !(order.can_cancel ?? REVERSIBLE_STATUSES.includes(order.status))}
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
                          className="orders-fk-primary-btn orders-fk-track-btn"
                          onClick={() => toggleTracking(order.order_id)}
                          aria-expanded={trackingOrders.has(order.order_id)}
                        >
                          {trackingOrders.has(order.order_id) ? 'Hide Tracking' : 'Track Order'}
                          <Truck size={14} />
                        </button>
                        <button
                          type="button"
                          className="orders-fk-details-btn"
                          onClick={() => toggleOrder(order.order_id)}
                          aria-expanded={isOpen}
                          aria-controls={'order-details-' + order.order_id}
                        >
                          {isOpen ? 'Hide Details' : 'View Details'}
                          {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                      </div>
                    </div>

                    {isOpen && (
                      <div className="orders-fk-details" id={'order-details-' + order.order_id}>
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
                          <div>
                            <span>Payment method</span>
                            <strong>{String(order.payment_method || 'COD').toUpperCase() === 'COD' ? 'Cash on delivery' : String(order.payment_method || 'Online payment').toUpperCase()}</strong>
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
                                disabled={reviewSubmittingId === order.order_id}
                              >
                                {reviewSubmittingId === order.order_id ? 'Publishing…' : 'Publish review'} <Sparkles size={14} />
                              </button>
                            </div>
                          </div>
                        )}

                        <div className="orders-fk-items">
                          <div className="orders-fk-items-heading">
                            <strong>Items in this order</strong>
                            <span>{order.items.length} {order.items.length === 1 ? 'item' : 'items'}</span>
                          </div>
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
                                  {resolveOrderImage(item.image_url || item.product_image_url) ? (
                                    <img
                                      src={resolveOrderImage(item.image_url || item.product_image_url)}
                                      alt=""
                                      loading="lazy"
                                    />
                                  ) : (
                                    <Package size={18} aria-hidden="true" />
                                  )}
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
                        <div className="orders-fk-price-summary" aria-label="Order price breakdown">
                          <div>
                            <span>Subtotal</span>
                            <strong>{formatCurrency(Number(order.subtotal ?? (Number(order.total_amount || 0) - Number(order.online_setup_fee || 0))))}</strong>
                          </div>
                          {Number(order.online_setup_fee || 0) > 0 && (
                            <div>
                              <span>Online setup / service fee</span>
                              <strong>{formatCurrency(Number(order.online_setup_fee || 0))}</strong>
                            </div>
                          )}
                          <div className="orders-fk-price-total">
                            <span>Order total</span>
                            <strong>{formatCurrency(order.total_amount)}</strong>
                          </div>
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

      <AnimatePresence>
        {cancelCandidate && (
          <motion.div
            className="orders-fk-modal-backdrop"
            role="presentation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget && cancelingOrderId === null) {
                setCancelCandidate(null);
                setCancelDialogError('');
              }
            }}
          >
            <motion.section
              className="orders-fk-cancel-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="orders-fk-cancel-title"
              aria-describedby="orders-fk-cancel-description"
              ref={cancelDialogRef}
              tabIndex={-1}
              initial={{ opacity: 0, y: 14, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.99 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              onMouseDown={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="orders-fk-dialog-close"
                onClick={() => {
                  if (cancelingOrderId === null) {
                    setCancelCandidate(null);
                    setCancelDialogError('');
                  }
                }}
                aria-label="Close cancellation dialog"
                disabled={cancelingOrderId !== null}
              >
                <X size={17} />
              </button>
              <span className="orders-fk-dialog-eyebrow">ORDER CANCELLATION</span>
              <div className="orders-fk-dialog-icon"><AlertCircle size={22} /></div>
              <h2 id="orders-fk-cancel-title">Cancel Order #{cancelCandidate.order_id}?</h2>
              <p id="orders-fk-cancel-description">
                The shop will be notified and reserved stock will be released only if the server accepts cancellation.
                Only pending or accepted orders are eligible.
              </p>
              {String(cancelCandidate.payment_status || '').toUpperCase() === 'PAID' && (
                <div className="orders-fk-refund-note">
                  This order is marked as paid. Cancellation is not an automatic refund; the shop may need to follow up on the refund.
                </div>
              )}
              {cancelDialogError && <div className="orders-fk-dialog-error" role="alert">{cancelDialogError}</div>}
              <div className="orders-fk-dialog-actions">
                <button
                  type="button"
                  className="orders-fk-dialog-keep"
                  onClick={() => {
                    setCancelCandidate(null);
                    setCancelDialogError('');
                  }}
                  disabled={cancelingOrderId !== null}
                >
                  Keep order
                </button>
                <button
                  type="button"
                  className="orders-fk-dialog-confirm"
                  ref={cancelConfirmButtonRef}
                  onClick={() => void confirmCancelOrder()}
                  disabled={cancelingOrderId !== null}
                >
                  {cancelingOrderId === cancelCandidate.order_id ? 'Cancelling…' : 'Confirm cancellation'}
                  {cancelingOrderId === cancelCandidate.order_id ? <RefreshCw size={15} className="spin" /> : <Ban size={15} />}
                </button>
              </div>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
