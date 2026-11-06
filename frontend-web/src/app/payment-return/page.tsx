'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertCircle, CheckCircle2, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { API_BASE } from '../../lib/api';
import { useCart } from '../../context/CartContext';

type CashfreeCheckout = {
  checkout(options: {
    paymentSessionId: string;
    redirectTarget?: '_self' | '_blank' | '_top' | '_modal';
  }): Promise<unknown>;
};

type CashfreeFactory = (options: { mode: 'sandbox' | 'production' }) => CashfreeCheckout;

declare global {
  interface Window {
    Cashfree?: CashfreeFactory;
  }
}

type PendingOrder = {
  shopId?: number | string;
  checkoutSessionKey?: string;
  orderId?: string;
};

function loadCashfreeSdk(): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Cashfree checkout requires a browser.'));
  }
  if (window.Cashfree) return Promise.resolve();

  return new Promise((resolve, reject) => {
    let script = document.querySelector<HTMLScriptElement>(
      'script[data-retail-mind-cashfree="true"]',
    );
    const onLoad = () => {
      if (window.Cashfree) resolve();
      else reject(new Error('Cashfree checkout SDK could not be initialized.'));
    };
    const onError = () => reject(new Error('Unable to load Cashfree checkout. Check your connection and retry.'));

    if (!script) {
      script = document.createElement('script');
      script.src = 'https://sdk.cashfree.com/js/v3/cashfree.js';
      script.async = true;
      script.dataset.retailMindCashfree = 'true';
      script.addEventListener('load', onLoad, { once: true });
      script.addEventListener('error', onError, { once: true });
      document.head.appendChild(script);
      return;
    }

    script.addEventListener('load', onLoad, { once: true });
    script.addEventListener('error', onError, { once: true });
  });
}

function parseRetailMindOrderId(providerOrderId: string): string | null {
  const match = /^rm_order_(\d+)(?:_[a-f0-9]{8})?$/.exec(providerOrderId.trim());
  return match?.[1] ?? null;
}

export default function CashfreePaymentReturnPage() {
  const router = useRouter();
  const { clearCart } = useCart();
  const clearCartRef = useRef(clearCart);
  const didStartVerification = useRef(false);
  useEffect(() => {
    clearCartRef.current = clearCart;
  }, [clearCart]);

  const [orderId, setOrderId] = useState('');
  const [pending, setPending] = useState<PendingOrder | null>(null);
  const [checking, setChecking] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [paid, setPaid] = useState(false);
  const [refundRequired, setRefundRequired] = useState(false);
  const [message, setMessage] = useState('Verifying your payment securely with Retail Mind and Cashfree…');

  const finishPaidOrder = useCallback((id: string, pendingOrder: PendingOrder | null) => {
    setPaid(true);
    setRefundRequired(false);
    setMessage('Payment verified. Your order is confirmed.');

    const storedOrder = pendingOrder;
    if (storedOrder?.checkoutSessionKey) {
      sessionStorage.removeItem(storedOrder.checkoutSessionKey);
    }
    sessionStorage.removeItem(`cashfree:pending:${id}`);
    clearCartRef.current();

    const shopId = storedOrder?.shopId;
    if (shopId !== undefined && String(shopId).trim() !== '') {
      router.replace(`/shop/${shopId}/order-success?orderId=${id}`);
    } else {
      router.replace('/orders');
    }
  }, [router]);

  const checkPayment = useCallback(async (id: string, pendingOrder: PendingOrder | null, attempts = 1) => {
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace(`/auth?next=${encodeURIComponent('/payment-return?order_id=rm_order_' + id)}`);
      return;
    }

    setChecking(true);
    setMessage('Verifying your payment securely with Retail Mind and Cashfree…');
    setRefundRequired(false);

    try {
      for (let attempt = 0; attempt < attempts; attempt++) {
        const response = await fetch(
          `${API_BASE}/store/order/${encodeURIComponent(id)}/cashfree/status`,
          {
            headers: { Authorization: `Bearer ${token}` },
            cache: 'no-store',
          },
        );
        const data = await response.json();

        if (response.status === 401 || response.status === 403) {
          localStorage.removeItem('customerToken');
          router.replace(`/auth?next=${encodeURIComponent('/payment-return?order_id=rm_order_' + id)}`);
          return;
        }
        if (!response.ok) {
          throw new Error(data.detail || 'The payment status could not be checked.');
        }
        if (data.paid === true) {
          finishPaidOrder(id, pendingOrder);
          return;
        }
        if (data.refund_required === true) {
          setRefundRequired(true);
          setMessage('Cashfree received a payment for an order that can no longer be fulfilled. The shop must review the refund.');
          return;
        }
        if (attempt < attempts - 1) {
          await new Promise((resolve) => window.setTimeout(resolve, 1800));
        }
      }
      setMessage('Cashfree has not confirmed this payment yet. Your order remains unpaid until the server verifies a successful transaction.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to verify payment right now.');
    } finally {
      setChecking(false);
    }
  }, [finishPaidOrder, router]);

  useEffect(() => {
    if (didStartVerification.current) return;
    didStartVerification.current = true;
    const params = new URLSearchParams(window.location.search);
    const providerOrderId = params.get('order_id') || params.get('orderId') || '';
    const internalOrderId = parseRetailMindOrderId(providerOrderId);
    if (!internalOrderId) {
      setChecking(false);
      setMessage('The Cashfree return URL does not contain a valid Retail Mind order reference. Open My Orders to check your latest order.');
      return;
    }

    let savedPending: PendingOrder | null = null;
    const rawPending = sessionStorage.getItem(`cashfree:pending:${internalOrderId}`);
    if (rawPending) {
      try {
        savedPending = JSON.parse(rawPending) as PendingOrder;
      } catch {
        savedPending = null;
      }
    }
    setOrderId(internalOrderId);
    setPending(savedPending);
    void checkPayment(internalOrderId, savedPending, 5);
  }, [checkPayment]);

  const retryCheckout = async () => {
    if (!orderId || retrying) return;
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace(`/auth?next=${encodeURIComponent('/payment-return?order_id=rm_order_' + orderId)}`);
      return;
    }

    setRetrying(true);
    setMessage('Opening your secure Cashfree checkout…');
    try {
      const response = await fetch(
        `${API_BASE}/store/order/${encodeURIComponent(orderId)}/cashfree/session`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          cache: 'no-store',
        },
      );
      const data = await response.json();
      if (!response.ok || data.success !== true || !data.payment_session_id) {
        throw new Error(data.detail || 'A new checkout session could not be created.');
      }
      await loadCashfreeSdk();
      if (!window.Cashfree) throw new Error('Cashfree checkout SDK is unavailable.');
      const cashfree = window.Cashfree({
        mode: data.environment === 'production' ? 'production' : 'sandbox',
      });
      await cashfree.checkout({
        paymentSessionId: String(data.payment_session_id),
        redirectTarget: '_self',
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Unable to retry checkout.');
    } finally {
      setRetrying(false);
    }
  };

  return (
    <main style={{
      minHeight: '70vh',
      display: 'grid',
      placeItems: 'center',
      padding: '48px 20px',
    }}>
      <section style={{
        width: '100%',
        maxWidth: 520,
        border: '1px solid #e5e7eb',
        borderRadius: 24,
        padding: 32,
        background: '#fff',
        boxShadow: '0 16px 48px rgba(15, 23, 42, 0.08)',
      }}>
        <div style={{
          width: 56,
          height: 56,
          borderRadius: 18,
          display: 'grid',
          placeItems: 'center',
          background: paid ? '#dcfce7' : refundRequired ? '#fee2e2' : '#eff6ff',
          color: paid ? '#15803d' : refundRequired ? '#b91c1c' : '#1d4ed8',
          marginBottom: 20,
        }}>
          {paid
            ? <CheckCircle2 size={28} />
            : refundRequired
              ? <AlertCircle size={28} />
              : checking || retrying
                ? <Loader2 size={28} className="spin" />
                : <ShieldCheck size={28} />}
        </div>
        <p style={{ color: '#64748b', fontSize: 12, fontWeight: 700, letterSpacing: 1.4, margin: 0 }}>
          RETAIL MIND · SECURE PAYMENT
        </p>
        <h1 style={{ color: '#0f172a', fontSize: 26, fontWeight: 800, margin: '8px 0 12px' }}>
          {paid ? 'Payment successful' : refundRequired ? 'Refund review required' : checking ? 'Checking payment' : 'Payment not confirmed yet'}
        </h1>
        <p style={{ color: '#475569', lineHeight: 1.65, marginBottom: 24 }}>{message}</p>
        {orderId && (
          <p style={{ color: '#64748b', fontSize: 13, marginBottom: 22 }}>
            Retail Mind order <strong style={{ color: '#0f172a' }}>#{orderId}</strong>
          </p>
        )}
        {!paid && !refundRequired && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <button
              type="button"
              onClick={() => void checkPayment(orderId, pending, 3)}
              disabled={!orderId || checking || retrying}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                border: 0,
                borderRadius: 12,
                padding: '12px 16px',
                background: '#14532d',
                color: '#fff',
                fontWeight: 700,
                cursor: 'pointer',
                opacity: checking || retrying ? 0.6 : 1,
              }}
            >
              <RefreshCw size={16} /> Check payment
            </button>
            <button
              type="button"
              onClick={() => void retryCheckout()}
              disabled={!orderId || retrying || checking}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                border: '1px solid #cbd5e1',
                borderRadius: 12,
                padding: '12px 16px',
                background: '#fff',
                color: '#0f172a',
                fontWeight: 700,
                cursor: 'pointer',
                opacity: checking || retrying ? 0.6 : 1,
              }}
            >
              {retrying ? <Loader2 size={16} className="spin" /> : <ShieldCheck size={16} />}
              Retry secure checkout
            </button>
          </div>
        )}
        {refundRequired && (
          <p style={{ color: '#991b1b', fontSize: 13 }}>
            Do not pay again for this order. Keep your payment reference and contact the shop to arrange the refund.
          </p>
        )}
        <button
          type="button"
          onClick={() => router.replace('/orders')}
          style={{
            display: 'block',
            marginTop: 18,
            border: 0,
            background: 'transparent',
            color: '#475569',
            padding: '8px 0',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          Go to My Orders
        </button>
      </section>
    </main>
  );
}
