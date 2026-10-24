'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { motion, useReducedMotion } from 'framer-motion';
import {
  ArrowLeft, Check, CheckCircle2, ChevronRight, Package,
  RefreshCw, ShieldCheck, ShoppingBag, Truck, Headphones, MapPin, XCircle, RotateCcw,
  Sparkles, Clock, Store,
} from 'lucide-react';
import { API_BASE } from '../../../lib/api';
import ProductImage from '../../../components/ProductImage';
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

function getStatusCopy(status: string) {
  switch (status.toUpperCase()) {
    case 'DELIVERED':
      return { title: 'Order Delivered', text: 'Your order has been delivered successfully. Thank you for shopping local.' };
    case 'DISPATCHED':
    case 'OUT_FOR_DELIVERY':
      return { title: 'Order Out for Delivery', text: 'The shop has dispatched your order and the courier is en route to your address.' };
    case 'PACKED':
    case 'PREPARING':
    case 'ACCEPTED':
    case 'CONFIRMED':
      return { title: 'Order Being Prepared', text: 'The shop is picking and packaging your items with care.' };
    case 'CANCELLED':
      return { title: 'Order Cancelled', text: 'This order was cancelled. Reserved inventory was released.' };
    case 'REJECTED':
      return { title: 'Order Not Accepted', text: 'The shop was unable to accept this order.' };
    case 'RETURNED':
      return { title: 'Order Returned', text: 'The return request has been recorded and processed.' };
    default:
      return { title: 'Order Placed', text: 'Waiting for the shop to confirm your order details.' };
  }
}

export default function CustomerOrderTrackingPage() {
  const shouldReduceMotion = Boolean(useReducedMotion());
  const params = useParams<{ orderId: string }>();
  const router = useRouter();
  const orderId = String(params?.orderId || '');
  const [order, setOrder] = useState<CustomerOrder | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  const loadOrder = useCallback(async (isRefresh = false) => {
    if (!orderId) return;
    const token = typeof window !== 'undefined' ? localStorage.getItem('customerToken') : null;
    if (!token) {
      router.push('/auth');
      return;
    }
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError('');

    try {
      const response = await fetch(`${API_BASE}/store/orders/${orderId}`, {
        headers: { Authorization: 'Bearer ' + token },
        cache: 'no-store',
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.detail || 'Unable to load order #' + orderId);
      }
      setOrder(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unable to load order tracking details.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [orderId, router]);

  useEffect(() => {
    void loadOrder();
  }, [loadOrder]);

  const status = (order?.status || 'PENDING').toUpperCase();
  const isTerminal = status === 'CANCELLED' || status === 'REJECTED' || status === 'RETURNED';
  const stage = stageFor(status);
  const statusCopy = getStatusCopy(status);

  const itemsCount = useMemo(() => {
    return (order?.items || []).reduce((acc, item) => acc + (Number(item.quantity) || 1), 0);
  }, [order?.items]);

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <Link href="/orders" className={styles.backButton} aria-label="Back to orders">
              <ArrowLeft size={18} />
            </Link>
            <div>
              <span className={styles.headerKicker}>TRACK ORDER</span>
              <h1>Order #{orderId}</h1>
              {order?.shop_name && (
                <p className={styles.shopSubline}>
                  <Store size={13} /> {order.shop_name}
                </p>
              )}
            </div>
          </div>
          <button
            type="button"
            className={styles.refreshButton}
            onClick={() => void loadOrder(true)}
            disabled={refreshing}
            title="Refresh order status"
            aria-label="Refresh order status"
          >
            <RefreshCw size={15} className={refreshing ? styles.spinning : ''} />
            <span className={styles.refreshLabel}>Refresh</span>
          </button>
        </header>

        {loading ? (
          <div className={styles.loadingCard}>
            <div className={styles.loadingOrb} />
            <strong>Loading live tracking…</strong>
            <p>Fetching real-time dispatch status from the shop.</p>
          </div>
        ) : error ? (
          <div className={styles.errorCard}>
            <div className={styles.errorIcon}><XCircle size={28} /></div>
            <strong>Unable to load order tracking</strong>
            <p>{error}</p>
            <div className={styles.errorActions}>
              <button type="button" onClick={() => void loadOrder()} className={styles.primaryButton}>
                Try again
              </button>
              <Link href="/orders" className={styles.backLink}>Back to My Orders</Link>
            </div>
          </div>
        ) : order ? (
          <div className={styles.contentGrid}>
            {/* Left Column: Progress & Status */}
            <div className={styles.leftColumn}>
              {isTerminal ? (
                <motion.section
                  className={styles.terminalCard}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className={styles.terminalIcon}>
                    {status === 'RETURNED' ? <RotateCcw size={22} /> : <XCircle size={22} />}
                  </div>
                  <div>
                    <strong>{statusCopy.title}</strong>
                    <p>{statusCopy.text}</p>
                  </div>
                </motion.section>
              ) : (
                <motion.section
                  className={styles.timelineCard}
                  aria-label="Order progress"
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className={styles.timelineHead}>
                    <span className={styles.cardEyebrow}>LIVE DISPATCH PROGRESS</span>
                    <span className={styles.livePulseBadge}>
                      <span className={styles.pulseDot} />
                      Live Sync
                    </span>
                  </div>
                  <div className={styles.timeline}>
                    {STEPS.map((step, index) => {
                      const done = stage >= index;
                      const isCurrent = stage === index;
                      const Icon = step.icon;
                      return (
                        <div key={step.key} className={styles.step}>
                          <div className={styles.stepTop}>
                            <span
                              className={[
                                styles.stepNode,
                                done ? styles.stepDone : '',
                                isCurrent ? styles.stepCurrent : '',
                              ].filter(Boolean).join(' ')}
                            >
                              <Icon size={13} strokeWidth={2.5} />
                            </span>
                            {index < STEPS.length - 1 && (
                              <span
                                className={[
                                  styles.stepLine,
                                  stage > index ? styles.lineDone : '',
                                ].filter(Boolean).join(' ')}
                              />
                            )}
                          </div>
                          <span
                            className={[
                              styles.stepLabel,
                              isCurrent ? styles.stepLabelCurrent : '',
                              done ? styles.stepLabelDone : '',
                            ].filter(Boolean).join(' ')}
                          >
                            {step.label}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </motion.section>
              )}

              {/* Live Status Card */}
              <motion.section
                className={styles.statusCard}
                initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.08 }}
              >
                <div className={styles.statusCopy}>
                  <div className={styles.statusBadgeRow}>
                    <span className={styles.statusTag}>CURRENT STATUS</span>
                    <span className={styles.statusTime}>
                      <Clock size={12} /> {new Date(order.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <h2>{statusCopy.title}</h2>
                  <p>{statusCopy.text}</p>
                </div>

                <div className={styles.dispatchVehicleBox} aria-hidden="true">
                  <div className={styles.vehicleRoad}>
                    <span className={styles.roadDash} />
                    <span className={styles.roadDash} />
                    <span className={styles.roadDash} />
                  </div>
                  <div className={styles.vehicleIcon}>
                    <Truck size={28} />
                  </div>
                  <div className={styles.vehicleBeacon} />
                </div>
              </motion.section>

              {/* Delivery Address & Shop Card */}
              {order.delivery_address && (
                <motion.section
                  className={styles.addressCard}
                  initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, delay: 0.12 }}
                >
                  <div className={styles.addressIcon}><MapPin size={18} /></div>
                  <div className={styles.addressCopy}>
                    <strong>Destination</strong>
                    <p>{order.delivery_address}</p>
                  </div>
                </motion.section>
              )}
            </div>

            {/* Right Column: Order Items & Payment Receipt */}
            <div className={styles.rightColumn}>
              <motion.section
                className={styles.itemsCard}
                initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.05 }}
              >
                <div className={styles.sectionHeading}>
                  <div>
                    <span className={styles.cardEyebrow}>ORDER SUMMARY</span>
                    <h2>Ordered Items</h2>
                  </div>
                  <span className={styles.itemsCountBadge}>
                    {itemsCount} item{itemsCount === 1 ? '' : 's'}
                  </span>
                </div>

                <div className={styles.itemsList}>
                  {(order.items || []).map((item, index) => {
                    const quantity = Number(item.quantity || 0);
                    const unit = Number(item.unit_price ?? item.price ?? 0);
                    const lineTotal = Number(item.line_total ?? unit * quantity);
                    const name = getItemName(item);

                    return (
                      <div className={styles.itemRow} key={String(item.product_id) + '-' + index}>
                        <div className={styles.itemThumb}>
                          <ProductImage
                            src={item.image_url}
                            name={name}
                            className={styles.itemImg}
                          />
                        </div>
                        <div className={styles.itemInfo}>
                          <strong>{name}</strong>
                          <span>Qty {quantity} × {formatMoney(unit)}</span>
                        </div>
                        <b className={styles.itemTotal}>{formatMoney(lineTotal)}</b>
                      </div>
                    );
                  })}
                </div>

                <div className={styles.orderTotal}>
                  <div className={styles.subtotalRow}>
                    <span>Items Subtotal</span>
                    <strong>{formatMoney(order.total_amount)}</strong>
                  </div>
                  <div className={styles.subtotalRow}>
                    <span>Delivery Fee</span>
                    <strong className={styles.freeFee}>Free Local Delivery</strong>
                  </div>
                  <div className={styles.totalLine}>
                    <span>Total Paid</span>
                    <b>{formatMoney(order.total_amount)}</b>
                  </div>
                  {order.payment_method && (
                    <div className={styles.paymentMethodPill}>
                      <ShieldCheck size={13} /> Paid via {order.payment_method.toUpperCase()}
                    </div>
                  )}
                </div>
              </motion.section>

              <div className={styles.sideActions}>
                <Link href="/contact" className={styles.helpButton}>
                  <Headphones size={16} /> Need help with this order?
                </Link>
                <p className={styles.footerNote}>
                  <ShieldCheck size={14} /> Verified local merchant fulfillment via Retail Mind
                </p>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </main>
  );
}
