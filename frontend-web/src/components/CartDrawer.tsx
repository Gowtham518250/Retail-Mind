'use client';

import React, { useState } from 'react';
import { MapPin, Loader2, ShoppingCart, X, Minus, Plus, CheckCircle, AlertCircle } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { API_BASE } from '../lib/api';
import confetti from 'canvas-confetti';

export default function CartDrawer() {
  const { cartItems, isCartOpen, toggleCart, updateQuantity, cartTotal, clearCart } = useCart();
  const [address, setAddress]         = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLocating, setIsLocating]   = useState(false);
  const [error, setError]             = useState('');
  const [success, setSuccess]         = useState('');

  // ── Geolocation ────────────────────────────────────────────────────────────
  const handleGetLocation = () => {
    if (!navigator.geolocation) { setError('Geolocation not supported by your browser'); return; }
    setIsLocating(true);
    setError('');
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${coords.latitude}&lon=${coords.longitude}`
          );
          const data = await res.json();
          setAddress(data?.display_name || `${coords.latitude.toFixed(4)}, ${coords.longitude.toFixed(4)}`);
        } catch {
          setAddress(`${coords.latitude.toFixed(4)}, ${coords.longitude.toFixed(4)}`);
        } finally {
          setIsLocating(false);
        }
      },
      () => {
        setIsLocating(false);
        setError('Location permission denied. Please enter address manually.');
      }
    );
  };

  // ── Place Order ────────────────────────────────────────────────────────────
  const handlePlaceOrder = async () => {
    if (!address.trim()) { setError('Delivery address is required'); return; }

    const token = typeof window !== 'undefined' ? localStorage.getItem('customerToken') : null;
    if (!token) { setError('You must be logged in to place an order.'); return; }

    setError('');
    setIsSubmitting(true);

    const payload = {
      shop_id: 1,
      items: cartItems.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity,
      })),
      delivery_address: address.trim(),
    };

    try {
      const res = await fetch(`${API_BASE}/store/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Failed to place order. Please try again.');

      setSuccess('🎉 Order placed successfully!');
      confetti({ particleCount: 160, spread: 75, origin: { y: 0.55 }, colors: ['#6366f1', '#22d3ee', '#facc15'] });
      clearCart();
      setTimeout(() => { setSuccess(''); toggleCart(); }, 2500);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      {/* Overlay */}
      <div
        className="drawer-overlay"
        onClick={toggleCart}
        aria-hidden="true"
        style={{
          position: 'fixed', inset: 0,
          background: 'rgba(0,0,0,0.65)',
          backdropFilter: 'blur(6px)',
          zIndex: 998,
          transition: 'opacity 0.35s ease, visibility 0.35s ease',
          opacity: isCartOpen ? 1 : 0,
          visibility: isCartOpen ? 'visible' : 'hidden',
        }}
      />

      {/* Drawer */}
      <aside
        className={`cart-drawer ${isCartOpen ? 'open' : ''}`}
        aria-label="Shopping cart"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="cart-head">
          <div className="cart-head-left">
            <ShoppingCart size={20} />
            <h2 className="cart-head-title">Your Cart</h2>
            {cartItems.length > 0 && (
              <span className="cart-count-pill">{cartItems.reduce((s, i) => s + i.quantity, 0)}</span>
            )}
          </div>
          <button className="cart-close" onClick={toggleCart} aria-label="Close cart">
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="cart-scroll">
          {cartItems.length === 0 ? (
            <div className="cart-empty">
              <ShoppingCart size={52} style={{ opacity: 0.2 }} />
              <p>Your cart is empty</p>
              <small>Add items from the store to get started</small>
            </div>
          ) : (
            <div className="cart-items-list">
              {cartItems.map(item => (
                <div key={item.product.id} className="cart-item">
                  <div className="cart-item-info">
                    <div className="cart-item-name">{item.product.name}</div>
                    <div className="cart-item-price">₹{(item.product.price * item.quantity).toFixed(2)}</div>
                    <div className="cart-item-unit-price">₹{Number(item.product.price).toFixed(2)} each</div>
                  </div>
                  <div className="qty-controls">
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, -1)} aria-label="Decrease">
                      <Minus size={14} />
                    </button>
                    <span className="qty-val">{item.quantity}</span>
                    <button className="qty-btn" onClick={() => updateQuantity(item.product.id, 1)} aria-label="Increase">
                      <Plus size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {cartItems.length > 0 && (
          <div className="cart-foot">
            {/* Total */}
            <div className="cart-total-row">
              <span className="cart-total-label">Order Total</span>
              <span className="cart-total-val">₹{cartTotal.toFixed(2)}</span>
            </div>

            {/* Location button */}
            <button className="locate-btn" onClick={handleGetLocation} disabled={isLocating}>
              {isLocating
                ? <><Loader2 size={16} className="spin" />Locating…</>
                : <><MapPin size={16} />Use My Location</>
              }
            </button>

            {/* Address textarea */}
            <div className="addr-wrap">
              <MapPin size={15} className="addr-icon" />
              <textarea
                className="addr-input"
                value={address}
                onChange={e => setAddress(e.target.value)}
                placeholder="Delivery address (required)…"
                rows={2}
                aria-label="Delivery address"
              />
            </div>

            {/* Error / Success */}
            {error && (
              <div className="cart-banner error">
                <AlertCircle size={15} style={{ flexShrink: 0 }} /> {error}
              </div>
            )}
            {success && (
              <div className="cart-banner success">
                <CheckCircle size={15} style={{ flexShrink: 0 }} /> {success}
              </div>
            )}

            {/* Place order */}
            <button
              className="place-order-btn"
              onClick={handlePlaceOrder}
              disabled={isSubmitting || !!success}
              id="place-order-btn"
            >
              {isSubmitting ? <><span className="btn-spinner" /> Processing…</> : '🛍️ Place Order'}
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
