'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ArrowLeft, Check, CheckCircle2, Clock3, MapPin, Package, RefreshCw,
  ShoppingBag, Truck, Wifi, WifiOff, XCircle,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';
import { useWebLanguage } from '../../context/LanguageContext';

interface OrderItem {
  product_id: number;
  product_name?: string;
  name?: string;
  quantity: number;
  unit_price?: number;
  price?: number;
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

const STATUS_STEPS = ['PENDING', 'ACCEPTED', 'DISPATCHED', 'DELIVERED'] as const;

const statusMeta: Record<string, { label: keyof ReturnType<typeof useWebLanguage>['t']; description: keyof ReturnType<typeof useWebLanguage>['t']; icon: typeof Clock3 }> = {
  PENDING: { label: 'orderPlaced', description: 'orderPlacedDesc', icon: Clock3 },
  ACCEPTED: { label: 'acceptedPreparing', description: 'acceptedPreparingDesc', icon: Package },
  DISPATCHED: { label: 'outForDelivery', description: 'outForDeliveryDesc', icon: Truck },
  DELIVERED: { label: 'delivered', description: 'deliveredDesc', icon: CheckCircle2 },
  REJECTED: { label: 'rejected', description: 'rejectedDesc', icon: XCircle },
};

function normalizeStatus(status?: string) {
  const s = (status || 'PENDING').toUpperCase();
  if (s === 'CONFIRMED') return 'ACCEPTED';
  if (s === 'SHIPPED') return 'DISPATCHED';
  if (s === 'CANCELLED') return 'REJECTED';
  return s;
}

function buildWebSocketUrl(customerId: string, token: string) {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = '/ws/customer/' + encodeURIComponent(customerId);
  url.search = '?token=' + encodeURIComponent(token);
  return url.toString();
}

export default function MyOrdersPage() {
  const { t } = useWebLanguage();
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [live, setLive] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [notice, setNotice] = useState('');
  const router = useRouter();

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(false);
  const orderCountRef = useRef(0);

  const fetchOrders = useCallback(async (showSpinner = false) => {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }
    if (showSpinner) setRefreshing(true);

    try {
      const response = await fetch(API_BASE + '/store/my-orders', {
        cache: 'no-store',
        headers: { Authorization: 'Bearer ' + token },
      });

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem('customerToken');
          localStorage.removeItem('customerId');
          router.push('/auth');
          return;
        }
        throw new Error('Failed to load your orders.');
      }

      const data = await response.json();
      const nextOrders = Array.isArray(data.orders) ? data.orders : [];
      if (!mountedRef.current) return;

      setOrders(nextOrders);
      orderCountRef.current = nextOrders.length;
      setError('');
      setLastUpdated(new Date());
    } catch (err: any) {
      if (mountedRef.current && orderCountRef.current === 0) {
        setError(err.message || 'Unable to load your orders.');
      }
    } finally {
      if (mountedRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, [router]);

  const mergeRealtimeOrder = useCallback((payload: any) => {
    const id = Number(payload?.order_id);
    if (!id) return;

    setOrders(prev => {
      const found = prev.find(order => order.order_id === id);
      const nextStatus = normalizeStatus(payload.status);

      if (!found) {
        return [{
          order_id: id,
          shop_id: Number(payload.shop_id || 0),
          shop_name: payload.shop_name || 'Retail Mind Shop',
          status: nextStatus,
          total_amount: Number(payload.total_amount || 0),
          delivery_address: payload.delivery_address || '',
          items: Array.isArray(payload.items) ? payload.items : [],
          created_at: payload.created_at || new Date().toISOString(),
        }, ...prev];
      }

      return prev.map(order => order.order_id === id ? {
        ...order,
        status: nextStatus,
        total_amount: payload.total_amount ?? order.total_amount,
        items: Array.isArray(payload.items) && payload.items.length ? payload.items : order.items,
        shop_name: payload.shop_name || order.shop_name,
        created_at: payload.created_at || order.created_at,
      } : order);
    });

    setLastUpdated(new Date());

    const nextMeta = statusMeta[normalizeStatus(payload.status)];
    if (nextMeta) {
      setNotice('Order #' + id + ': ' + t(nextMeta.label));
      window.setTimeout(() => setNotice(''), 3500);
    }
  }, [t]);

  const startPolling = useCallback(() => {
    if (pollTimerRef.current) return;
    fetchOrders(false);
    pollTimerRef.current = setInterval(() => fetchOrders(false), 8000);
  }, [fetchOrders]);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const connectRealtime = useCallback(() => {
    const token = localStorage.getItem('customerToken');
    const customerId = localStorage.getItem('customerId');

    if (!token || !customerId || !mountedRef.current) {
      startPolling();
      return;
    }

    try {
      socketRef.current?.close();

      const socket = new WebSocket(buildWebSocketUrl(customerId, token));
      socketRef.current = socket;

      socket.onopen = () => {
        if (!mountedRef.current) return;
        setLive(true);
        stopPolling();

        heartbeatRef.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 20000);
      };

      socket.onmessage = event => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'order_status_changed' || payload.type === 'online_order_created') {
            mergeRealtimeOrder(payload);
          }
        } catch {
          // Keep the connection alive when a non-JSON heartbeat payload arrives.
        }
      };

      socket.onerror = () => {
        if (mountedRef.current) setLive(false);
      };

      socket.onclose = () => {
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }
        if (!mountedRef.current) return;

        setLive(false);
        startPolling();

        if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = setTimeout(connectRealtime, 5000);
      };
    } catch {
      setLive(false);
      startPolling();
      reconnectTimerRef.current = setTimeout(connectRealtime, 5000);
    }
  }, [mergeRealtimeOrder, startPolling, stopPolling]);

  useEffect(() => {
    mountedRef.current = true;
    fetchOrders();
    connectRealtime();

    return () => {
      mountedRef.current = false;
      stopPolling();
      socketRef.current?.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, [connectRealtime, fetchOrders, stopPolling]);

  const sortedOrders = useMemo(
    () => [...orders].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()),
    [orders],
  );

  return (
    <div className="container orders-page">
      <div className="orders-topbar">
        <div>
          <div className="orders-kicker">{t('customerAccount')}</div>
          <h1>{t('myOrders')}</h1>
          <p>{t('trackEveryOrder')}</p>
        </div>

        <div className="orders-live-stack">
          <span className={'live-pill ' + (live ? 'live' : 'offline')}>
            {live ? <Wifi size={14} /> : <WifiOff size={14} />}
            {live ? t('liveUpdates') : t('fallbackSync')}
          </span>
          <button className="orders-refresh" onClick={() => fetchOrders(true)} disabled={refreshing}>
            <RefreshCw size={15} className={refreshing ? 'spin' : ''} />
            {t('refresh')}
          </button>
        </div>
      </div>

      <div className="orders-subbar">
        <button className="hero-cta orders-back" onClick={() => router.back()}>
          <ArrowLeft size={16} /> {t('back')}
        </button>
        <span>
          {lastUpdated
            ? 'Updated ' + lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            : t('syncing')}
        </span>
      </div>

      <AnimatePresence>
        {notice && (
          <motion.div
            className="orders-live-notice"
            initial={{ opacity: 0, y: -12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -12 }}
          >
            <CheckCircle2 size={17} /> {notice}
          </motion.div>
        )}
      </AnimatePresence>

      {loading ? (
        <div className="orders-grid">
          {[1, 2, 3].map(i => <div key={i} className="order-skeleton" />)}
        </div>
      ) : error && !sortedOrders.length ? (
        <div className="orders-error">
          <XCircle size={28} />
          <h2>{t('couldntLoadOrders')}</h2>
          <p>{error}</p>
          <button className="hero-cta" onClick={() => fetchOrders(true)}>
            <RefreshCw size={15} /> {t('tryAgain')}
          </button>
        </div>
      ) : !sortedOrders.length ? (
        <div className="orders-empty">
          <div className="orders-empty-icon"><ShoppingBag size={42} /></div>
          <h2>{t('noOrders')}</h2>
          <p>{t('ordersEmpty')}</p>
          <button className="hero-cta" onClick={() => router.push('/')}>{t('startShopping')}</button>
        </div>
      ) : (
        <div className="orders-grid">
          {sortedOrders.map(order => {
            const status = normalizeStatus(order.status);
            const meta = statusMeta[status] || statusMeta.PENDING;
            const Icon = meta.icon;
            const currentIndex = STATUS_STEPS.indexOf(status as any);
            const rejected = status === 'REJECTED';

            return (
              <motion.article
                key={order.order_id}
                layout
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35 }}
                className={'order-card ' + (rejected ? 'rejected' : '')}
              >
                <div className="order-card-head">
                  <div>
                    <span className="order-number">ORDER #{order.order_id}</span>
                    <h2>{order.shop_name || 'Shop #' + order.shop_id}</h2>
                    <p>{new Date(order.created_at).toLocaleString()}</p>
                  </div>
                  <div className="order-status-badge">
                    <Icon size={16} /> {t(meta.label)}
                  </div>
                </div>

                <div className="order-status-banner">
                  <div className="status-banner-icon"><Icon size={24} /></div>
                  <div>
                    <strong>{t(meta.label)}</strong>
                    <span>{t(meta.description)}</span>
                  </div>
                </div>

                <div className="order-timeline">
                  {STATUS_STEPS.map((step, index) => {
                    const StepIcon = statusMeta[step].icon;
                    const reached = !rejected && currentIndex >= index;

                    return (
                      <div className={'timeline-node ' + (reached ? 'reached' : '')} key={step}>
                        <div className="timeline-node-dot">
                          {reached ? <Check size={14} /> : <StepIcon size={14} />}
                        </div>
                        <span>{t(statusMeta[step].label)}</span>
                        {index < STATUS_STEPS.length - 1 && (
                          <div className={'timeline-connector ' + (reached && currentIndex > index ? 'filled' : '')} />
                        )}
                      </div>
                    );
                  })}
                  {rejected && (
                    <div className="timeline-rejected">
                      <XCircle size={15} /> Rejected
                    </div>
                  )}
                </div>

                <div className="order-card-content">
                  <section>
                    <h3><Package size={15} /> {t('items')}</h3>
                    <div className="order-items">
                      {order.items.map((item, idx) => {
                        const name = item.product_name || item.name || 'Product #' + item.product_id;
                        const price = Number(item.unit_price ?? item.price ?? 0);
                        return (
                          <div className="order-item-row" key={order.order_id + '-' + item.product_id + '-' + idx}>
                            <div>
                              <strong>{name}</strong>
                              <span>{t('qty')} ×{item.quantity}</span>
                            </div>
                            <strong>₹{(price * item.quantity).toFixed(2)}</strong>
                          </div>
                        );
                      })}
                    </div>
                  </section>

                  <section className="order-card-grid">
                    <div>
                      <h3><MapPin size={15} /> {t('deliveryAddress')}</h3>
                      <p>{order.delivery_address}</p>
                    </div>
                    <div>
                      <h3><ShoppingBag size={15} /> {t('total')}</h3>
                      <p className="order-total">₹{Number(order.total_amount).toFixed(2)}</p>
                    </div>
                  </section>
                </div>

                <div className="order-card-footer">
                  <span>Your live order tracking stays active while your account is connected.</span>
                  <button
                    className="hero-cta"
                    onClick={() => router.push('/shop/' + order.shop_id + '/order-success?orderId=' + order.order_id)}
                  >
                    {t('trackOrder')} <Truck size={15} />
                  </button>
                </div>
              </motion.article>
            );
          })}
        </div>
      )}
    </div>
  );
}
