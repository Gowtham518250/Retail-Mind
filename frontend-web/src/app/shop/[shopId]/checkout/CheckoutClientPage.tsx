'use client';

import { useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft, User, Phone, MapPin, Home, Banknote,
  ShieldCheck, Loader2, AlertCircle, ShoppingBag,
} from 'lucide-react';
import { useCart } from '../../../../context/CartContext';
import { API_BASE } from '../../../../lib/api';
import type { PlacedOrder } from '../../../../lib/types';

interface FormState {
  name: string;
  phone: string;
  email: string;
  city: string;
  pincode: string;
  address: string;
  landmark: string;
  notes: string;
}

const initialForm: FormState = {
  name: '', phone: '', email: '', city: '', pincode: '', address: '', landmark: '', notes: '',
};

export default function CheckoutClientPage() {
  const params = useParams();
  const router = useRouter();
  const shopId = Number(params?.shopId || 8);
  const { cartItems, cartTotal, clearCart } = useCart();

  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitError, setSubmitError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const deliveryFee = cartTotal >= 499 || cartTotal === 0 ? 0 : 29;
  const grandTotal = cartTotal + deliveryFee;

  const combinedAddress = useMemo(() => (
    [form.address, form.landmark ? `Landmark: ${form.landmark}` : '', form.city, form.pincode]
      .filter(Boolean)
      .join(', ')
  ), [form.address, form.landmark, form.city, form.pincode]);

  const setField = (key: keyof FormState) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setForm((prev) => ({ ...prev, [key]: e.target.value }));
    setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  const detectLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser.');
      return;
    }
    setLocationError('');
    setIsDetectingLocation(true);
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        try {
          const res = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat=${coords.latitude}&lon=${coords.longitude}`
          );
          if (!res.ok) throw new Error('reverse geocoding failed');
          const data = await res.json();
          const address = data.address || {};
          setForm((prev) => ({
            ...prev,
            address: [address.house_number, address.road, address.neighbourhood || address.suburb]
              .filter(Boolean).join(' ').trim(),
            city: address.city || address.town || address.village || address.county || '',
            pincode: address.postcode || '',
          }));
        } catch {
          setLocationError('Unable to resolve your location. Please enter it manually.');
        } finally {
          setIsDetectingLocation(false);
        }
      },
      () => {
        setIsDetectingLocation(false);
        setLocationError('Unable to detect location. Please enter it manually.');
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };

  const validate = () => {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (form.name.trim().length < 2) next.name = 'Enter your full name';
    if (!/^\d{10}$/.test(form.phone.trim())) next.phone = 'Enter a valid 10-digit phone number';
    if (form.email.trim() && !/^\S+@\S+\.\S+$/.test(form.email.trim())) next.email = 'Enter a valid email';
    if (!form.city.trim()) next.city = 'City is required';
    if (!/^\d{6}$/.test(form.pincode.trim())) next.pincode = 'Enter a valid 6-digit pincode';
    if (form.address.trim().length < 5) next.address = 'Enter your full address';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handlePlaceOrder = async () => {
    if (!cartItems.length || !validate()) return;
    setSubmitError('');
    setIsSubmitting(true);

    const payload = {
      shop_id: shopId,
      customer_name: form.name.trim(),
      phone: form.phone.trim(),
      delivery_address: combinedAddress,
      items: cartItems.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
      payment_method: 'COD',
    };

    try {
      const res = await fetch(`${API_BASE}/store/guest-order`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || data.message || 'Could not place your order. Please try again.');

      const placedOrder: PlacedOrder = {
        order_id: data.order_id,
        shop_name: data.shop_name,
        total_amount: data.total_amount,
        status: data.status || 'PENDING',
        payment_method: 'COD',
        customer_name: form.name.trim(),
        phone: form.phone.trim(),
        delivery_address: combinedAddress,
        items: cartItems.map((item) => ({
          name: item.product.name,
          quantity: item.quantity,
          price: item.product.price,
        })),
        placed_at: new Date().toISOString(),
      };

      sessionStorage.setItem(`order:${data.order_id}`, JSON.stringify({
        ...placedOrder,
        tracking_token: data.tracking_token,
      }));
      clearCart();
      router.push(`/shop/${shopId}/order-success?orderId=${data.order_id}`);
    } catch (err: any) {
      setSubmitError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!cartItems.length) {
    return (
      <div className="container" style={{ padding: '48px 20px' }}>
        <div className="store-empty-state">Your cart is empty. Add a few products before checking out.</div>
        <div style={{ marginTop: 18 }}>
          <button className="hero-cta" onClick={() => router.push(`/shop/${shopId}`)}>
            <ArrowLeft size={16} /> Back to shop
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container" style={{ padding: '28px 20px 90px' }}>
      <button className="hero-cta" style={{ width: 'fit-content', marginBottom: 20 }} onClick={() => router.push(`/shop/${shopId}`)}>
        <ArrowLeft size={16} /> Back to shop
      </button>

      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="checkout-grid">
        <div className="checkout-main">
          <section className="checkout-card">
            <h2 className="checkout-card-title"><MapPin size={18} /> Delivery details</h2>
            <div className="checkout-field-row">
              <div className="checkout-field">
                <label><User size={14} /> Full name</label>
                <input value={form.name} onChange={setField('name')} placeholder="Your name" />
                {errors.name && <span className="field-error">{errors.name}</span>}
              </div>
              <div className="checkout-field">
                <label><Phone size={14} /> Phone number</label>
                <input value={form.phone} onChange={setField('phone')} placeholder="10-digit mobile number" inputMode="numeric" maxLength={10} />
                {errors.phone && <span className="field-error">{errors.phone}</span>}
              </div>
            </div>
            <div className="checkout-field">
              <label>Email <span className="field-optional">(optional)</span></label>
              <input value={form.email} onChange={setField('email')} placeholder="you@example.com" />
              {errors.email && <span className="field-error">{errors.email}</span>}
            </div>
            <div className="checkout-field">
              <label><Home size={14} /> Address</label>
              <div className="location-row">
                <textarea value={form.address} onChange={setField('address')} placeholder="House / flat no, street, area" rows={2} />
                <button type="button" className="location-button" onClick={detectLocation} disabled={isDetectingLocation}>
                  {isDetectingLocation ? 'Detecting…' : 'Detect location'}
                </button>
              </div>
              {errors.address && <span className="field-error">{errors.address}</span>}
              {locationError && <span className="field-error">{locationError}</span>}
            </div>
            <div className="checkout-field-row">
              <div className="checkout-field">
                <label>City</label>
                <input value={form.city} onChange={setField('city')} placeholder="City" />
                {errors.city && <span className="field-error">{errors.city}</span>}
              </div>
              <div className="checkout-field">
                <label>Pincode</label>
                <input value={form.pincode} onChange={setField('pincode')} placeholder="6-digit pincode" inputMode="numeric" maxLength={6} />
                {errors.pincode && <span className="field-error">{errors.pincode}</span>}
              </div>
            </div>
            <div className="checkout-field">
              <label>Landmark <span className="field-optional">(optional)</span></label>
              <input value={form.landmark} onChange={setField('landmark')} placeholder="Nearby landmark" />
            </div>
            <div className="checkout-field">
              <label>Order notes <span className="field-optional">(optional)</span></label>
              <textarea value={form.notes} onChange={setField('notes')} placeholder="Any delivery instructions" rows={2} />
            </div>
          </section>

          <section className="checkout-card">
            <h2 className="checkout-card-title"><Banknote size={18} /> Payment method</h2>
            <div className="payment-options">
              <div className="payment-option active" aria-label="Cash on Delivery selected">
                <Banknote size={20} />
                <div>
                  <strong>Cash on Delivery</strong>
                  <span>Pay when your order arrives</span>
                </div>
              </div>
            </div>
            <p className="payment-note">Online UPI and card payments are not enabled yet. No payment is captured online.</p>
          </section>
        </div>

        <aside className="checkout-summary">
          <h2 className="checkout-card-title"><ShoppingBag size={18} /> Order summary</h2>
          <div className="summary-items">
            {cartItems.map((item) => (
              <div key={item.product.id} className="summary-item">
                <span>{item.product.name} <em>×{item.quantity}</em></span>
                <span>₹{(item.product.price * item.quantity).toFixed(2)}</span>
              </div>
            ))}
          </div>
          <div className="summary-row"><span>Subtotal</span><span>₹{cartTotal.toFixed(2)}</span></div>
          <div className="summary-row"><span>Delivery</span><span>{deliveryFee === 0 ? 'FREE' : `₹${deliveryFee.toFixed(2)}`}</span></div>
          <div className="summary-row muted"><span>GST</span><span>Included</span></div>
          <div className="summary-row total"><span>Total</span><span>₹{grandTotal.toFixed(2)}</span></div>
          {submitError && <div className="cart-banner error"><AlertCircle size={15} /> {submitError}</div>}
          <button className="place-order-btn" onClick={handlePlaceOrder} disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 size={16} className="spin" /> Placing order…</> : 'Place Order'}
          </button>
          <div className="checkout-trust"><ShieldCheck size={14} /> Secure guest checkout · No account needed</div>
        </aside>
      </motion.div>
    </div>
  );
}
