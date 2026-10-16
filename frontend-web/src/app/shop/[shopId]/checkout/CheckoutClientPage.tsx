'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import {
  ArrowLeft, MapPin, Home, Banknote,
  ShieldCheck, Loader2, AlertCircle, ShoppingBag, UserRound, LockKeyhole,
  LocateFixed, CheckCircle2, Sparkles,
} from 'lucide-react';
import { useCart } from '../../../../context/CartContext';
import { API_BASE } from '../../../../lib/api';

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
  const shopId = Number(params?.shopId || 0);
  const { cartItems, cartTotal, clearCart } = useCart();

  const [form, setForm] = useState<FormState>(initialForm);
  const [customer, setCustomer] = useState<CustomerProfile | null>(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitError, setSubmitError] = useState('');
  const [locationError, setLocationError] = useState('');
  const [locationSuccess, setLocationSuccess] = useState('');
  const [isDetectingLocation, setIsDetectingLocation] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [onlineSetupFee, setOnlineSetupFee] = useState(0);
  const [deliveryFee, setDeliveryFee] = useState(0);
  const [minOrder, setMinOrder] = useState(0);
  const [offerDelivery, setOfferDelivery] = useState(true);
  const [acceptCod, setAcceptCod] = useState(false);
  const [acceptOnline, setAcceptOnline] = useState(false);
  const [shopSettingsLoading, setShopSettingsLoading] = useState(true);
  const [couponCode, setCouponCode] = useState('');
  const [couponDiscount, setCouponDiscount] = useState(0);
  const [couponMessage, setCouponMessage] = useState('');
  const [couponLoading, setCouponLoading] = useState(false);

  const checkoutSessionKey = useMemo(
    () => `retail-mind:checkout-idempotency:${shopId}:${cartItems
      .map((item) => `${item.product.id}:${item.quantity}`)
      .sort()
      .join('|')}`,
    [shopId, cartItems],
  );

  const grandTotal =
    Math.max(0, cartTotal - couponDiscount)
    + (offerDelivery ? deliveryFee : 0)
    + onlineSetupFee;

  useEffect(() => {
    let cancelled = false;
    if (!Number.isSafeInteger(shopId) || shopId <= 0) {
      setSubmitError('This shop link is invalid. Choose a shop from the marketplace.');
      setAuthChecking(false);
      router.replace('/');
      return;
    }

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
        if (!res.ok) throw new Error('Shop settings request failed.');
        const data = await res.json();
        if (!cancelled) {
          setOnlineSetupFee(Math.max(0, Number(data.online_setup_fee || 0)));
          setDeliveryFee(Math.max(0, Number(data.delivery_fee || 0)));
          setMinOrder(Math.max(0, Number(data.min_order || 0)));
          setOfferDelivery(data.offer_delivery !== false);
          setAcceptCod(data.accept_cod === true);
          setAcceptOnline(data.accept_online === true);
          setShopSettingsLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setShopSettingsLoading(false);
          setSubmitError('We could not verify this shop’s checkout settings. Reload this page before placing an order.');
        }
      });

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
    if (key === 'address' || key === 'city' || key === 'pincode') {
      setLocationSuccess('');
    }
  };

  const detectLocation = () => {
    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser.');
      return;
    }
    setLocationError('');
    setLocationSuccess('');
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
          const detectedAddress = [address.house_number, address.road, address.neighbourhood || address.suburb]
            .filter(Boolean).join(' ').trim();
          const detectedCity = address.city || address.town || address.village || address.county || '';
          const detectedPincode = address.postcode || '';
          setForm((prev) => ({
            ...prev,
            address: detectedAddress || prev.address,
            city: detectedCity || prev.city,
            pincode: detectedPincode || prev.pincode,
          }));
          if (detectedAddress || detectedCity || detectedPincode) {
            setLocationSuccess('Location found. Check your house number and delivery details before ordering.');
          } else {
            setLocationError('We found your coordinates but could not read the address. Please enter it manually.');
          }
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
    if (shopSettingsLoading) {
      setSubmitError('Please wait while we verify this shop’s checkout settings.');
      return false;
    }
    if (!acceptCod) {
      setSubmitError(acceptOnline
        ? 'Online payment is not integrated yet. This shop cannot accept a website order until Cash on Delivery is enabled.'
        : 'This shop has not enabled a supported checkout payment method.');
      return false;
    }
    if (minOrder > 0 && cartTotal < minOrder) {
      setSubmitError(
        'Minimum online order is ₹' + minOrder.toFixed(2) +
        '. Add ₹' + Math.max(0, minOrder - cartTotal).toFixed(2) + ' more.',
      );
      return false;
    }
    if (offerDelivery) {
      if (!form.city.trim()) next.city = 'City is required';
      if (!/^\d{6}$/.test(form.pincode.trim())) next.pincode = 'Enter a valid 6-digit pincode';
      if (form.address.trim().length < 5) next.address = 'Enter your full address';
    }
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
    if (!customer || !cartItems.length) return;
    if (cartItems.some((item) => Number(item.product.shop_id) !== shopId)) {
      setSubmitError('Your cart contains an item from another shop. Return to that shop and check out its cart separately.');
      return;
    }
    if (cartItems.some((item) => item.product.stock_available !== undefined && Number(item.product.stock_available) <= 0)) {
      setSubmitError('Your cart contains an out-of-stock item. Remove it before placing this order.');
      return;
    }
    if (!validate()) return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace(`/auth?next=${encodeURIComponent(`/shop/${shopId}/checkout`)}`);
      return;
    }

    setSubmitError('');
    setIsSubmitting(true);

    const payload = {
      shop_id: shopId,
      items: cartItems.map((item) => ({ product_id: item.product.id, quantity: item.quantity })),
      delivery_address: combinedAddress,
      coupon_code: couponCode.trim().toUpperCase() || undefined,
      idempotency_key: (() => {
        const existing = sessionStorage.getItem(checkoutSessionKey);
        if (existing) return existing;
        const created = 'web-' + shopId + '-' + crypto.randomUUID();
        sessionStorage.setItem(checkoutSessionKey, created);
        return created;
      })(),
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

      sessionStorage.removeItem(checkoutSessionKey);
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

      <div className="checkout-stepper" aria-label="Checkout progress">
        <div className="checkout-step is-complete"><span>1</span><b>Address</b></div>
        <span className="checkout-step-line" aria-hidden="true" />
        <div className="checkout-step is-active" aria-current="step"><span>2</span><b>Review</b></div>
        <span className="checkout-step-line" aria-hidden="true" />
        <div className="checkout-step"><span>3</span><b>Confirm</b></div>
      </div>

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
              <label><Home size={14} /> Delivery address</label>
              <div className="location-row">
                <textarea value={form.address} onChange={setField('address')} placeholder="House / flat no, street, area" rows={2} />
                <button type="button" className="location-button" onClick={detectLocation} disabled={isDetectingLocation}>
                  <span className="location-button-icon">
                    {isDetectingLocation
                      ? <Loader2 size={17} className="spin" />
                      : locationSuccess
                        ? <CheckCircle2 size={17} />
                        : <LocateFixed size={17} />}
                  </span>
                  <span className="location-button-copy">
                    <strong>{isDetectingLocation ? 'Finding your address…' : locationSuccess ? 'Update detected address' : 'Use my current location'}</strong>
                    <small>{isDetectingLocation ? 'Waiting for your device location' : 'Fill city and pincode automatically'}</small>
                  </span>
                  {!isDetectingLocation && <span className="location-button-tag">GPS</span>}
                </button>
              </div>
              {locationSuccess && <span className="location-success"><CheckCircle2 size={14} /> {locationSuccess}</span>}
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
              {acceptCod && (
                <div className="payment-option active" aria-label="Cash on Delivery available">
                  <Banknote size={20} />
                  <div>
                    <strong>Cash on Delivery</strong>
                    <span>Pay when your order arrives</span>
                  </div>
                </div>
              )}
              {acceptOnline && (
                <div className="payment-option" aria-label="Online payment configured">
                  <ShieldCheck size={20} />
                  <div>
                    <strong>Online payment unavailable</strong>
                    <span>Online checkout is not integrated in this storefront. Use Cash on Delivery when the shop supports it.</span>
                  </div>
                </div>
              )}
            </div>
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
          <div className="summary-row">
            <span>Delivery</span>
            <span>{!offerDelivery ? 'Not offered' : deliveryFee === 0 ? 'FREE' : '₹' + deliveryFee.toFixed(2)}</span>
          </div>
          <div className="summary-row">
            <span>Online setup / service</span>
            <span>₹{onlineSetupFee.toFixed(2)}</span>
          </div>
          {minOrder > 0 && (
            <div className="checkout-trust">Minimum online order: ₹{minOrder.toFixed(2)}</div>
          )}
          <div className="checkout-coupon">
            <div className="checkout-coupon-heading"><span className="checkout-coupon-icon"><Sparkles size={15} /></span><span><strong>Have a shop coupon?</strong><small>Enter a code shared by this shopkeeper to unlock your discount.</small></span></div>
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
