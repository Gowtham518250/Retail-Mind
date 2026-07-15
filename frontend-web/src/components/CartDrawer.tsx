'use client';

import React, { useState } from 'react';
import { useCart } from '../context/CartContext';

export default function CartDrawer() {
  const { cartItems, isCartOpen, toggleCart, updateQuantity, cartTotal, clearCart } = useCart();
  const [address, setAddress] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLocating, setIsLocating] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  // Removed early return so CSS transitions can play
  const handleGetLocation = () => {
    if (!navigator.geolocation) {
      setError('Geolocation is not supported by your browser');
      return;
    }
    
    setIsLocating(true);
    setError('');

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          const { latitude, longitude } = position.coords;
          // Reverse geocode using OpenStreetMap Nominatim API
          const res = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`);
          const data = await res.json();
          if (data && data.display_name) {
            setAddress(data.display_name);
          } else {
            // Fallback if reverse geocoding fails
            setAddress(`Lat: ${latitude.toFixed(4)}, Lon: ${longitude.toFixed(4)}`);
          }
        } catch (err) {
          setError('Failed to fetch address from coordinates');
        } finally {
          setIsLocating(false);
        }
      },
      (err) => {
        setIsLocating(false);
        setError('Failed to get location. Please allow location permissions.');
      }
    );
  };

  const handlePlaceOrder = async () => {
    if (!address.trim()) {
      setError('Delivery address is required');
      return;
    }
    
    setError('');
    setIsSubmitting(true);
    
    const token = localStorage.getItem('customerToken');
    // Using default shop_id=1 as per current frontend implementation
    const payload = {
      shop_id: 1,
      items: cartItems.map(item => ({
        product_id: item.product.id,
        quantity: item.quantity
      })),
      delivery_address: address
    };

    try {
      const response = await fetch('/store/order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Failed to place order');
      }

      setSuccessMessage('Order placed successfully!');
      clearCart();
      setTimeout(() => {
        setSuccessMessage('');
        toggleCart();
      }, 2000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="drawer-overlay" onClick={toggleCart} style={{
        position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: 'rgba(0,0,0,0.6)', zIndex: 999, backdropFilter: 'blur(4px)',
        transition: 'opacity 0.4s ease, visibility 0.4s ease',
        opacity: isCartOpen ? 1 : 0,
        visibility: isCartOpen ? 'visible' : 'hidden'
      }} />
      <div className={`cart-drawer-container ${isCartOpen ? 'open' : ''}`}>
        
        {/* Header */}
        <div className="cart-header">
          <h2 className="cart-title">Your Cart</h2>
          <button className="cart-close-btn" onClick={toggleCart}>✕</button>
        </div>
        
        {/* Body (Scrollable Items) */}
        <div className="cart-body">
          {cartItems.length === 0 ? (
            <div style={{ textAlign: 'center', color: 'var(--text-secondary)', marginTop: '40px' }}>
              <div style={{ fontSize: '48px', marginBottom: '16px', opacity: 0.5 }}>🛒</div>
              <p>Your cart is empty</p>
            </div>
          ) : (
            cartItems.map(item => (
              <div key={item.product.id} className="cart-item-card">
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: '600', fontSize: '16px' }}>{item.product.name}</div>
                  <div style={{ color: 'var(--fk-blue)', fontSize: '14px', marginTop: '6px', fontWeight: '500' }}>₹{item.product.price.toFixed(2)}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'rgba(255,255,255,0.05)', padding: '4px', borderRadius: '24px' }}>
                  <button onClick={() => updateQuantity(item.product.id, -1)} style={{ width: '32px', height: '32px', borderRadius: '50%', border: 'none', background: 'rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer', fontSize: '16px' }}>−</button>
                  <span style={{ width: '20px', textAlign: 'center', fontWeight: '600' }}>{item.quantity}</span>
                  <button onClick={() => updateQuantity(item.product.id, 1)} style={{ width: '32px', height: '32px', borderRadius: '50%', border: 'none', background: 'rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer', fontSize: '16px' }}>+</button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer (Fixed at bottom) */}
        {cartItems.length > 0 && (
          <div className="cart-footer">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px', fontWeight: 'bold', fontSize: '20px' }}>
              <span>Total:</span>
              <span style={{ color: 'var(--fk-blue)' }}>₹{cartTotal.toFixed(2)}</span>
            </div>
            
            <button className="btn-exact-location" onClick={handleGetLocation} disabled={isLocating}>
              {isLocating ? (
                <svg className="spin-animation" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>
              )}
              {isLocating ? 'Locating...' : 'Use Exact Location'}
            </button>

            <div className="location-input-group">
              <svg className="location-input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>
              <textarea 
                className="location-input" 
                value={address} 
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Or enter delivery address manually..."
                rows={2}
              />
            </div>

            {error && <div style={{ color: '#ff4444', marginBottom: '16px', fontSize: '14px', background: 'rgba(255,0,0,0.1)', padding: '10px', borderRadius: '8px' }}>{error}</div>}
            {successMessage && <div style={{ color: '#00C853', marginBottom: '16px', fontSize: '14px', background: 'rgba(0,200,83,0.1)', padding: '10px', borderRadius: '8px', fontWeight: '500' }}>{successMessage}</div>}

            <button 
              className="btn-primary" 
              style={{ width: '100%', padding: '16px', fontSize: '16px', borderRadius: '12px', fontWeight: '700', letterSpacing: '0.5px' }}
              onClick={handlePlaceOrder}
              disabled={isSubmitting || !!successMessage}
            >
              {isSubmitting ? 'Processing...' : 'Place Order'}
            </button>
          </div>
        )}
      </div>
    </>
  );
}
