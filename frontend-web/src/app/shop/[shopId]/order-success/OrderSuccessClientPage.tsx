'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { motion } from 'framer-motion';
import confetti from 'canvas-confetti';
import {
  CheckCircle2, Clock, Package, Truck, Home, ShoppingBag, Phone, MapPin, RefreshCw,
} from 'lucide-react';
import { API_BASE } from '../../../../lib/api';
import type { PlacedOrder } from '../../../../lib/types';

const STAGES = [
  { key: 'PENDING', label: 'Order Confirmed', icon: CheckCircle2 },
  { key: 'ACCEPTED', label: 'Preparing', icon: Package },
  { key: 'DISPATCHED', label: 'Out for Delivery', icon: Truck },
  { key: 'DELIVERED', label: 'Delivered', icon: Home },
];

type StoredOrder = PlacedOrder & { tracking_token?: string };

export default function OrderSuccessClientPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const shopId = Number(params?.shopId || 8);
  const orderId = search?.get('orderId');

  const [order, setOrder] = useState<StoredOrder | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [trackingError, setTrackingError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const loadOrder = async () => {
      if (!orderId) {
        setNotFound(true);
        return;
      }

      const token = localStorage.getItem('customerToken');
      if (!token) {
        router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${orderId}`)}`);
        return;
      }

      setTrackingError('');

      try {
        const res = await fetch(
          `${API_BASE}/store/order/${encodeURIComponent(orderId)}/track`,
          {
            headers: { Authorization: `Bearer ${token}` },
            cache: 'no-store',
          },
        );

        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem('customerToken');
          router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${orderId}`)}`);
          return;
        }

        const data = await res.json();
        if (!res.ok) {
          if (res.status === 404) setNotFound(true);
          throw new Error(data.detail || 'Unable to load this order.');
        }

        if (cancelled) return;

        const stored = sessionStorage.getItem(`order:${orderId}`);
        let storedOrder: Partial<StoredOrder> = {};
        if (stored) {
          try {
            storedOrder = JSON.parse(stored);
          } catch {
            storedOrder = {};
          }
        }

        setOrder({
          order_id: Number(data.order_id),
          shop_name: data.shop_name || storedOrder.shop_name || `Shop #${data.shop_id}`,
          total_amount: Number(data.total_amount || 0),
          status: data.status || 'PENDING',
          payment_method: 'COD',
          customer_name: data.customer_name || storedOrder.customer_name || 'Customer',
          phone: data.customer_phone || storedOrder.phone || '',
          delivery_address: data.delivery_address || storedOrder.delivery_address || '',
          items: Array.isArray(data.items)
            ? data.items.map((item: any) => ({
                name: item.product_name || item.name || `Product #${item.product_id}`,
                quantity: Number(item.quantity || 0),
                price: Number(item.unit_price ?? item.price ?? 0),
              }))
            : storedOrder.items || [],
          placed_at: data.created_at || storedOrder.placed_at || new Date().toISOString(),
        });
        setLiveStatus(String(data.status || 'PENDING').toUpperCase());
      } catch (error: any) {
        if (!cancelled) {
          setTrackingError(error?.message || 'Unable to load order status right now.');
        }
      }
    };

    void loadOrder();

    return () => {
      cancelled = true;
    };
  }, [orderId, router, shopId]);

  useEffect(() => {
    if (!order) return;
    confetti({ particleCount: 160, spread: 75, origin: { y: 0.4 }, colors: ['#6366f1', '#22d3ee', '#facc15'] });
  }, [order]);

  const refreshStatus = async () => {
    if (!order) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${order.order_id}`)}`);
      return;
    }

    setIsRefreshing(true);
    setTrackingError('');
    try {
      const res = await fetch(
        `${API_BASE}/store/order/${order.order_id}/track`,
        { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' },
      );
      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem('customerToken');
        router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${order.order_id}`)}`);
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Unable to refresh order status right now.');
      }
      setLiveStatus(String(data.status || 'PENDING').toUpperCase());
      setOrder((current) => current ? {
        ...current,
        shop_name: data.shop_name || current.shop_name,
        status: data.status || current.status,
        total_amount: Number(data.total_amount ?? current.total_amount),
        delivery_address: data.delivery_address || current.delivery_address,
        items: Array.isArray(data.items)
          ? data.items.map((item: any) => ({
              name: item.product_name || item.name || `Product #${item.product_id}`,
              quantity: Number(item.quantity || 0),
              price: Number(item.unit_price ?? item.price ?? 0),
            }))
          : current.items,
      } : current);
    } catch (error: any) {
      setTrackingError(error.message || 'Unable to refresh order status right now.');
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!order) return;

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
          router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${order.order_id}`)}`);
          return;
        }

        const ticketResponse = await fetch(
          API_BASE + '/api/ws/token?shop_id=' + encodeURIComponent(String(shopId)),
          {
            headers: { Authorization: 'Bearer ' + token },
            cache: 'no-store',
          },
        );

        if (!ticketResponse.ok) {
          if (ticketResponse.status === 401 || ticketResponse.status === 403) {
            stopped = true;
            localStorage.removeItem('customerToken');
            router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/order-success?orderId=${order.order_id}`)}`);
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
          reconnectDelayMs = 1000;
        };

        socket.onmessage = (message) => {
          try {
            const event = JSON.parse(message.data);
            if (
              event?.type === 'order.status_changed' &&
              Number(event.order_id) === Number(order.order_id)
            ) {
              const nextStatus = String(event.status || 'PENDING').toUpperCase();
              setLiveStatus(nextStatus);
              setOrder((current) =>
                current
                  ? {
                      ...current,
                      status: nextStatus,
                      total_amount: Number(event.total_amount ?? current.total_amount),
                      delivery_address:
                        event.delivery_address || current.delivery_address,
                      items: Array.isArray(event.items)
                        ? event.items.map((item: any) => ({
                            name:
                              item.product_name ||
                              item.name ||
                              `Product #${item.product_id}`,
                            quantity: Number(item.quantity || 0),
                            price: Number(item.unit_price ?? item.price ?? 0),
                          }))
                        : current.items,
                    }
                  : current,
              );
              setTrackingError('');
            }
          } catch {
            // Manual refresh remains available if an event cannot be parsed.
          }
        };

        socket.onerror = () => {
          // Reconnect through onclose without starting REST polling.
        };

        socket.onclose = () => {
          socket = null;
          scheduleReconnect();
        };
      } catch {
        scheduleReconnect();
      }
    };

    void connectRealtime();

    return () => {
      stopped = true;
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
    };
  }, [order, router, shopId]);

  const activeStageIndex = Math.max(0, STAGES.findIndex((s) => s.key === (liveStatus || 'PENDING')));

  if (notFound) {
    return (
      <div className="container" style={{ padding: '48px 20px' }}>
        <div className="store-empty-state">We couldn't find that order. It may have already been viewed.</div>
        <div style={{ marginTop: 18 }}>
          <button className="hero-cta" onClick={() => router.push(`/shop/${shopId}`)}>
            <ShoppingBag size={16} /> Continue shopping
          </button>
        </div>
      </div>
    );
  }

  if (!order) return null;

  const placedDate = new Date(order.placed_at);
  const estStart = new Date(placedDate.getTime() + 45 * 60 * 1000);
  const estEnd = new Date(placedDate.getTime() + 90 * 60 * 1000);
  const fmt = (d: Date) => d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className="container" style={{ padding: '28px 20px 90px', maxWidth: 780 }}>
      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        className="success-card"
      >
        <div className="success-icon-wrap"><CheckCircle2 size={56} strokeWidth={1.5} /></div>
        <h1 className="success-title">Order placed successfully!</h1>
        <p className="success-sub">
          Thank you, {order.customer_name.split(' ')[0]}. {order.shop_name} has received your order.
        </p>

        <div className="success-meta-row">
          <div className="success-meta-pill"><span>Order ID</span><strong>#{order.order_id}</strong></div>
          <div className="success-meta-pill"><span>Estimated delivery</span><strong>{fmt(estStart)} – {fmt(estEnd)}</strong></div>
          <div className="success-meta-pill"><span>Payment</span><strong>Cash on Delivery</strong></div>
        </div>

        <div className="timeline-refresh-row">
          <span>Live order status</span>
          <button onClick={refreshStatus} disabled={isRefreshing} aria-label="Refresh status">
            <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} />
          </button>
        </div>
        {trackingError && <div className="cart-banner error">{trackingError}</div>}
        <div className="order-timeline">
          {STAGES.map((stage, index) => {
            const Icon = stage.icon;
            const reached = index <= activeStageIndex;
            return (
              <div key={stage.key} className={`timeline-step ${reached ? 'active' : 'pending'}`}>
                <div className="timeline-dot"><Icon size={16} /></div>
                <span>{stage.label}</span>
                {index < STAGES.length - 1 && <div className="timeline-line" />}
              </div>
            );
          })}
        </div>

        <div className="success-details-grid">
          <div className="success-detail-card">
            <h3><MapPin size={15} /> Delivering to</h3>
            <p>{order.customer_name}</p>
            <p className="muted">{order.delivery_address}</p>
            <p className="muted"><Phone size={12} /> {order.phone}</p>
          </div>
          <div className="success-detail-card">
            <h3><ShoppingBag size={15} /> Items ({order.items.length})</h3>
            {order.items.map((item, i) => (
              <p key={i} className="muted">{item.name} × {item.quantity} — ₹{(item.price * item.quantity).toFixed(2)}</p>
            ))}
            <p className="success-total">Total: ₹{order.total_amount.toFixed(2)}</p>
          </div>
        </div>

        <div className="success-actions">
          <button className="hero-cta" onClick={() => router.push(`/shop/${shopId}`)}>
            <ShoppingBag size={16} /> Continue shopping
          </button>
          <button className="store-link-btn" onClick={() => window.print()}>
            <Clock size={16} /> Download invoice
          </button>
        </div>
      </motion.div>
    </div>
  );
}
