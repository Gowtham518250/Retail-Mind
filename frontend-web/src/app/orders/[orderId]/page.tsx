'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft, Bike, Check, CheckCircle2, ChevronRight, Package,
  RefreshCw, ShieldCheck, ShoppingBag, Truck, Headphones, MapPin, XCircle, RotateCcw,
} from 'lucide-react';
import { API_BASE } from '../../../lib/api';
import styles from './tracking.module.css';

interface OrderItem {
  product_id: number;
  product_name?: string;
  name?: string;
  quantity: number;
  unit_price?: number;
  price?: number;
  line_total?: number;
  image_url?: string | null;
}
interface CustomerOrder {
  order_id: number;
  shop_id: number;
  shop_name?: string;
  status: string;
  total_amount: number;
  delivery_address?: string;
  items: OrderItem[];
  created_at: string;
  payment_status?: string;
  payment_method?: string;
}
const STEPS = [
  { key: 'PLACED', label: 'Placed', icon: Check },
  { key: 'CONFIRMED', label: 'Confirmed', icon: CheckCircle2 },
  { key: 'PACKED', label: 'Packed', icon: Package },
  { key: 'DISPATCHED', label: 'Out for Delivery', icon: Truck },
  { key: 'DELIVERED', label: 'Delivered', icon: CheckCircle2 },
];
const terminalStatuses = new Set(['CANCELLED', 'REJECTED', 'RETURNED']);

function stageFor(status: string) {
  switch (status.toUpperCase()) {
    case 'DELIVERED': return 4;
    case 'DISPATCHED':
    case 'OUT_FOR_DELIVERY': return 3;
    case 'PACKED':
    case 'PREPARING': return 2;
    case 'ACCEPTED':
    case 'CONFIRMED': return 1;
    default: return 0;
  }
}
function formatMoney(value: number) {
  const amount = Number(value);
  return '₹' + (Number.isFinite(amount) ? amount.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0');
}
function getItemName(item: OrderItem) {
  return item.product_name || item.name || 'Product';
}
function getItemIcon(item: OrderItem) {
  const name = getItemName(item).toLowerCase();
  if (name.includes('oil')) return '🫙';
  if (name.includes('rice') || name.includes('flour') || name.includes('sugar')) return '🌾';
  if (name.includes('fruit') || name.includes('apple')) return '🍎';
  return '🛍️';
}
function getStatusCopy(status: string) {
  switch (status.toUpperCase()) {
    case 'DELIVERED':
      return { title: 'Order Delivered', text: 'Your order has been delivered. Thank you for shopping local.' };
    case 'DISPATCHED':
    case 'OUT_FOR_DELIVERY':
      return { title: 'Your Order Is On Its Way', text: 'The shop has dispatched your order. Keep this screen handy for updates.' };
    case 'PACKED':
    case 'PREPARING':
    case 'ACCEPTED':
    case 'CONFIRMED':
      return { title: 'Order Is Being Prepared', text: 'Your order is being packed by the shop.' };
    case 'CANCELLED':
      return { title: 'Order Cancelled', text: 'This order was cancelled. Your order status is shown below.' };
    case 'REJECTED':
      return { title: 'Order Not Accepted', text: 'The shop could not accept this order.' };
    case 'RETURNED':
      return { title: 'Order Returned', text: 'The return has been recorded for this order.' };
    default:
      return { title: 'Order Placed', text: 'Your order is waiting for confirmation from the shop.' };
  }
}

export default function CustomerOrderTrackingPage() {
  const params = useParams<{ orderId: string }>();
  const router = useRouter();
  const orderId = String(params?.orderId || '');
  const [order, setOrder] = useState<CustomerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const loadOrder = useCallback(async (silent = false) => {
    if (!orderId || !/^\d+$/.test(orderId)) {
      setError('This order number is invalid.');
      setLoading(false);
      return;
    }
    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.replace('/auth?next=' + encodeURIComponent('/orders/' + orderId));
      return;
    }
    if (silent) setRefreshing(true);
    try {
      const response = await fetch(API_BASE + '/store/my-orders', {
        headers: { Authorization: 'Bearer ' + token },
        cache: 'no-store',
      });
      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('customerToken');
        router.replace('/auth?next=' + encodeURIComponent('/orders/' + orderId));
        return;
      }
      if (!response.ok) throw new Error('Unable to load this order right now.');
      const data = await response.json();
      const list: CustomerOrder[] = Array.isArray(data.orders) ? data.orders : [];
      const found = list.find((candidate) => String(candidate.order_id) === orderId);
      if (!found) throw new Error('We could not find this order in your account.');
      setOrder(found);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load this order right now.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [orderId, router]);

  useEffect(() => {
    void loadOrder();
    const timer = window.setInterval(() => void loadOrder(true), 30000);
    return () => window.clearInterval(timer);
  }, [loadOrder]);

  const status = String(order?.status || 'PENDING').toUpperCase();
  const stage = stageFor(status);
  const isTerminal = terminalStatuses.has(status);
  const statusCopy = useMemo(() => getStatusCopy(status), [status]);
  const itemsCount = (order?.items || []).reduce((sum, item) => sum + Number(item.quantity || 0), 0);

  return (
    <main className={styles.page} data-experience="order-tracking">
      <div className={styles.shell}>
        <header className={styles.header}>
          <Link href="/orders" className={styles.backButton} aria-label="Back to my orders">
            <ArrowLeft size={18} />
          </Link>
          <h1>{'Order #ORD-' + (orderId || '—')}</h1>
          <button type="button" className={styles.refreshButton} onClick={() => void loadOrder(true)} disabled={refreshing} aria-label="Refresh order status">
            <RefreshCw size={16} className={refreshing ? styles.spinning : ''} />
          </button>
        </header>

        {loading ? (
          <div className={styles.loadingCard} role="status">Loading your order…</div>
        ) : error ? (
          <section className={styles.errorCard} role="alert">
            <span className={styles.errorIcon}><Package size={25} /></span>
            <strong>Order details unavailable</strong>
            <p>{error}</p>
            <button type="button" onClick={() => void loadOrder()} className={styles.primaryButton}>Try again</button>
            <Link href="/orders" className={styles.backLink}>Back to My Orders</Link>
          </section>
        ) : order ? (
          <>
            {isTerminal ? (
              <section className={styles.terminalCard}>
                {status === 'RETURNED' ? <RotateCcw size={17} /> : <XCircle size={17} />}
                <div><strong>{statusCopy.title}</strong><p>{statusCopy.text}</p></div>
              </section>
            ) : (
              <section className={styles.timelineCard} aria-label="Order progress">
                <div className={styles.timeline}>
                  {STEPS.map((step, index) => {
                    const done = stage >= index;
                    const Icon = step.icon;
                    return (
                      <div key={step.key} className={styles.step}>
                        <div className={styles.stepTop}>
                          <span className={[styles.stepNode, done ? styles.stepDone : '', stage === index ? styles.stepCurrent : ''].filter(Boolean).join(' ')}>
                            <Icon size={11} strokeWidth={2.5} />
                          </span>
                          {index < STEPS.length - 1 && <span className={[styles.stepLine, stage > index ? styles.lineDone : ''].filter(Boolean).join(' ')} />}
                        </div>
                        <span className={[styles.stepLabel, stage === index ? styles.stepLabelCurrent : ''].filter(Boolean).join(' ')}>{step.label}</span>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            <section className={styles.statusCard}>
              <div className={styles.statusCopy}>
                <span className={styles.eyebrow}>ORDER STATUS</span>
                <h2>{statusCopy.title}</h2>
                <p>{statusCopy.text}</p>
                <div className={styles.statusMeta}>
                  <span className={styles.statusDot} />
                  <span>Updates automatically</span>
                </div>
              </div>
              <div className={styles.deliveryArt} aria-hidden="true">
                <span className={styles.artSun} />
                <span className={styles.artCloud} />
                <div className={styles.deliveryBike}><Bike size={61} strokeWidth={1.65} /></div>
                <div className={styles.deliveryBox}><ShoppingBag size={19} /></div>
              </div>
            </section>

            <section className={styles.itemsCard}>
              <div className={styles.sectionHeading}>
                <h2>Order Items</h2>
                <span>{itemsCount} item{itemsCount === 1 ? '' : 's'}</span>
              </div>
              <div className={styles.itemsList}>
                {(order.items || []).map((item, index) => {
                  const quantity = Number(item.quantity || 0);
                  const unit = Number(item.unit_price ?? item.price ?? 0);
                  const lineTotal = Number(item.line_total ?? unit * quantity);
                  return (
                    <div className={styles.itemRow} key={String(item.product_id) + '-' + index}>
                      <div className={styles.itemThumb}>
                        {item.image_url ? <img src={item.image_url} alt="" loading="lazy" /> : <span>{getItemIcon(item)}</span>}
                      </div>
                      <div className={styles.itemInfo}>
                        <strong>{getItemName(item)}</strong>
                        <span>Qty {quantity} × {formatMoney(unit)}</span>
                      </div>
                      <b className={styles.itemTotal}>{formatMoney(lineTotal)}</b>
                    </div>
                  );
                })}
              </div>
              <div className={styles.orderTotal}>
                <div><span>Items ({itemsCount})</span><strong>{formatMoney(order.total_amount)}</strong></div>
                <div className={styles.totalLine}><span>Total</span><b>{formatMoney(order.total_amount)}</b></div>
              </div>
            </section>

            {order.delivery_address && (
              <section className={styles.addressCard}>
                <span><MapPin size={16} /></span>
                <div><strong>Delivery Address</strong><p>{order.delivery_address}</p></div>
                <ChevronRight size={16} />
              </section>
            )}

            <Link href="/contact" className={styles.helpButton}>
              <Headphones size={16} /> Need Help?
            </Link>
            <p className={styles.footerNote}><ShieldCheck size={13} /> Secure order updates from Retail Mind</p>
          </>
        ) : null}
      </div>
    </main>
  );
}
