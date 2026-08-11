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

export default function OrderSuccessClientPage() {
  const params = useParams();
  const search = useSearchParams();
  const router = useRouter();
  const shopId = Number(params?.shopId || 8);
  const orderId = search?.get('orderId');

  const [order, setOrder] = useState<PlacedOrder | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [liveStatus, setLiveStatus] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  useEffect(() => {
    if (!orderId) { setNotFound(true); return; }
    const raw = sessionStorage.getItem(`order:${orderId}`);
    if (!raw) { setNotFound(true); return; }
    try {
      setOrder(JSON.parse(raw));
    } catch {
      setNotFound(true);
    }
  }, [orderId]);

  useEffect(() => {
    if (!order) return;
    confetti({ particleCount: 160, spread: 75, origin: { y: 0.4 }, colors: ['#6366f1', '#22d3ee', '#facc15'] });
  }, [order]);

  const refreshStatus = async () => {
    if (!order) return;
    setIsRefreshing(true);
    try {
      const res = await fetch(
        `${API_BASE}/store/order/${order.order_id}/guest-track?phone=${encodeURIComponent(order.phone)}`
      );
      if (res.ok) {
        const data = await res.json();
        setLiveStatus(data.status);
      }
    } catch {
      // Silently keep last known status — this is a non-critical enhancement.
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!order) return;
    refreshStatus();
    const interval = setInterval(refreshStatus, 15000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order]);

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
        <div className="success-icon-wrap">
          <CheckCircle2 size={56} strokeWidth={1.5} />
        </div>
        <h1 className="success-title">Order placed successfully!</h1>
        <p className="success-sub">
          Thank you, {order.customer_name.split(' ')[0]}. {order.shop_name} has received your order.
        </p>

        <div className="success-meta-row">
          <div className="success-meta-pill">
            <span>Order ID</span>
            <strong>#{order.order_id}</strong>
          </div>
          <div className="success-meta-pill">
            <span>Estimated delivery</span>
            <strong>{fmt(estStart)} – {fmt(estEnd)}</strong>
          </div>
          <div className="success-meta-pill">
            <span>Payment</span>
            <strong>{order.payment_method === 'COD' ? 'Cash on Delivery' : order.payment_method}</strong>
          </div>
        </div>

        {/* Timeline */}
        <div className="timeline-refresh-row">
          <span>Live order status</span>
          <button onClick={refreshStatus} disabled={isRefreshing} aria-label="Refresh status">
            <RefreshCw size={13} className={isRefreshing ? 'spin' : ''} />
          </button>
        </div>
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
