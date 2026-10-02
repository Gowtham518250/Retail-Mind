'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft, MapPin, Home, Banknote,
  ShieldCheck, Loader2, AlertCircle, ShoppingBag, UserRound, LockKeyhole,
} from 'lucide-react';
import { useCart } from '../../../../context/CartContext';
import { API_BASE } from '../../../../lib/api';
import type { PlacedOrder } from '../../../../lib/types';

interface FormState {
  city: string;
  pincode: string;
  address: string;
  landmark: string;
}

interface CustomerProfile {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  city?: string | null;
  address?: string | null;
}

const initialForm: FormState = {
  city: '', pincode: '', address: '', landmark: '',
};

export default function CheckoutClientPage() {
  const params = useParams();
  const router = useRouter();
  const shopId = Number(params?.shopId || 8);
  const { cartItems, cartTotal, clearCart } = useCart();

  const [form, setForm] = useState<FormState>(initialForm);
  const [customer, setCustomer] = useState<CustomerProfile | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitError, setSubmitError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [onlineSetupFee, setOnlineSetupFee] = useState(0);
  const [couponCode, setCouponCode] = useState('');
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponMessage, setCouponMessage] = useState('');
  const [couponLoading, setCouponLoading] = useState(false);

  const deliveryFee = 0 as number;
  const grandTotal = Math.max(0, cartTotal - couponDiscount) + onlineSetupFee;

  useEffect(() => {
    let cancelled = false;

    const requireCustomer = async () => {
      const token = localStorage.getItem('customerToken');
      if (!token) {
        router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`);
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/store/customer/me`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });

        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem('customerToken');
          localStorage.removeItem('customerName');
          localStorage.removeItem('customerEmail');
          router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`);
          return;
        }

        const data = await res.json();
        if (!res.ok || !data.customer) {
          throw new Error(data.detail || 'Unable to load your customer account.');
        }

        if (cancelled) return;

        const profile = data.customer as CustomerProfile;
        setCustomer(profile);
        setForm((prev) => ({
          ...prev,
          city: profile.city || '',
          address: profile.address || '',
        }));
      } catch (error: any) {
        if (!cancelled) {
          setSubmitError(error?.message || 'Unable to verify your customer account.');
        }
      } finally {
        if (!cancelled) {
          setAuthChecking(false);
        }
      }
    };

    void requireCustomer();

    void fetch(API_BASE + '/store/shops/' + shopId + '/products?limit=1', {
      cache: 'no-store',
    })
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        if (!cancelled) {
          setOnlineSetupFee(Math.max(0, Number(data.online_setup_fee || 0)));
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [router, shopId]);

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
    if (!form.city.trim()) next.city = 'City is required';
    if (!/^\d{6}$/.test(form.pincode.trim())) next.pincode = 'Enter a valid 6-digit pincode';
    if (form.address.trim().length < 5) next.address = 'Enter your full address';
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const applyCoupon = async () => {
    const code = couponCode.trim().toUpperCase();
    if (!code) {
      setCouponMessage('Enter a coupon code.');
      setCouponDiscount(0);
      return;
    }
    setCouponLoading(true);
    setCouponMessage('');
    try {
      const res = await fetch(API_BASE + '/store/coupon/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shop_id: shopId, code, subtotal: cartTotal }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Coupon could not be applied.');
      setCouponDiscount(Number(data.discount || 0));
      setCouponMessage(data.message || 'Coupon applied.');
    } catch (error: any) {
      setCouponDiscount(0);
      setCouponMessage(error?.message || 'Coupon could not be applied.');
    } finally {
      setCouponLoading(false);
    }
  };

  const handlePlaceOrder = async () => {
    if (!customer || !cartItems.length || !validate()) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`);
      return;
    }

    setSubmitError('');
    setIsSubmitting(true);

    const cartSignature = JSON.stringify(
      cartItems
        .map((item) => ({ product_id: item.product.id, quantity: item.quantity }))
        .sort((a, b) => a.product_id - b.product_id),
    );
    const idempotencyStorageKey = 'checkout-idempotency:' + shopId;
    let idempotencyKey = '';
    try {
      const saved = sessionStorage.getItem(idempotencyStorageKey);
      if (saved) {
        const parsed = JSON.parse(saved) as { signature?: string; key?: string };
        if (parsed.signature === cartSignature && parsed.key) {
          idempotencyKey = parsed.key;
        }
      }
      if (!idempotencyKey) {
        idempotencyKey = 'web-' + shopId + '-' + crypto.randomUUID();
        sessionStorage.setItem(
          idempotencyStorageKey,
          JSON.stringify({ signature: cartSignature, key: idempotencyKey }),
        );
      }
    } catch {
      // sessionStorage can be unavailable in strict/privacy browser modes.
      idempotencyKey = 'web-' + shopId + '-' + crypto.randomUUID();
    }

    const payload = {
      shop_id: shopId,
      items: cartItems.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
      delivery_address: combinedAddress,
      coupon_code: couponCode.trim().toUpperCase() || undefined,
      idempotency_key: idempotencyKey,
    };

    try {
      const res = await fetch(`${API_BASE}/store/order`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();

      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem('customerToken');
        router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`);
        return;
      }

      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Could not place your order. Please try again.');
      }

      const placedOrder: PlacedOrder = {
        order_id: data.order_id,
        shop_name: data.shop_name,
        total_amount: Number(data.total_amount || grandTotal),
        status: data.status || 'PENDING',
        payment_method: 'COD',
        customer_name: customer.name,
        phone: customer.phone || '',
        delivery_address: combinedAddress,
        items: cartItems.map((item) => ({
          name: item.product.name,
          quantity: item.quantity,
          price: item.product.price,
        })),
        placed_at: new Date().toISOString(),
      };

      sessionStorage.setItem(`order:${data.order_id}`, JSON.stringify(placedOrder));
      try {
        sessionStorage.removeItem(idempotencyStorageKey);
      } catch {}
      clearCart();
      router.push(`/shop/${shopId}/order-success?orderId=${data.order_id}`);
    } catch (err: any) {
      setSubmitError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (authChecking) {
    return (
      <div className="container" style={{ padding: '72px 20px' }}>
        <div className="checkout-auth-gate">
          <div className="checkout-auth-icon"><LockKeyhole size={24} /></div>
          <h1>Secure checkout</h1>
          <p>Verifying your RetailShop customer account and loading your delivery details.</p>
        </div>
      </div>
    );
  }

  if (!customer) {
    return (
      <div className="container" style={{ padding: '48px 20px' }}>
        <div className="store-empty-state">
          {submitError || 'Please sign in to continue to checkout.'}
        </div>
        <div style={{ marginTop: 18 }}>
          <button className="hero-cta" onClick={() => router.push(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`)}>
            <UserRound size={16} /> Sign in to checkout
          </button>
        </div>
      </div>
    );
  }

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
            <div className="checkout-account-card">
              <div className="checkout-account-icon"><UserRound size={18} /></div>
              <div className="checkout-account-copy">
                <strong>{customer.name}</strong>
                <span>{customer.email || 'Customer account'}</span>
                {customer.phone && <span>+91 {customer.phone}</span>}
              </div>
              <span className="checkout-account-badge">Signed in</span>
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
          {onlineSetupFee > 0 && (
            <div className="summary-row">
              <span>Online setup / service</span>
              <span>₹{onlineSetupFee.toFixed(2)}</span>
            </div>
          )}
          <div className="checkout-coupon">
            <div className="checkout-coupon-row">
              <input
                value={couponCode}
                onChange={(e) => setCouponCode(e.target.value)}
                placeholder="Coupon code"
                maxLength={50}
              />
              <button type="button" onClick={applyCoupon} disabled={couponLoading}>
                {couponLoading ? 'Checking…' : 'Apply'}
              </button>
            </div>
            {couponMessage && <div className={couponDiscount > 0 ? 'checkout-coupon-success' : 'checkout-coupon-message'}>{couponMessage}</div>}
          </div>
          {couponDiscount > 0 && (
            <div className="summary-row discount"><span>Coupon discount</span><span>-₹{couponDiscount.toFixed(2)}</span></div>
          )}
          <div className="summary-row muted"><span>GST</span><span>Included</span></div>
          <div className="summary-row total"><span>Total</span><span>₹{grandTotal.toFixed(2)}</span></div>
          {submitError && <div className="cart-banner error"><AlertCircle size={15} /> {submitError}</div>}
          <button className="place-order-btn" onClick={handlePlaceOrder} disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 size={16} className="spin" /> Placing order…</> : 'Place Order'}
          </button>
          <div className="checkout-trust"><ShieldCheck size={14} /> Secure account checkout · Your order will appear in My Orders</div>
        </aside>
      </motion.div>
    </div>
  );
}
