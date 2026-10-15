'use client';

import { useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AnimatePresence, motion, useSpring, useTransform } from 'framer-motion';
import { ArrowRight, Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './CartDrawer.module.css';

function Money({ value }: { value: number }) {
  const spring = useSpring(value, { stiffness: 150, damping: 22 });
  useEffect(() => { spring.set(value); }, [value, spring]);
  const text = useTransform(spring, (v) => '₹' + v.toFixed(2));
  return <motion.span>{text}</motion.span>;
}

export default function CartDrawer() {
  const { cartItems, isCartOpen, toggleCart, updateQuantity, removeFromCart, cartTotal, cartMessage, clearCartMessage, setCartMessage } = useCart();
  const router = useRouter();
  const params = useParams();
  const shopId = Number(params?.shopId || 0);
  const closeRef = useRef<HTMLButtonElement>(null);
  const count = cartItems.reduce((s, i) => s + i.quantity, 0);
  const hasUnavailableItems = cartItems.some((item) => item.product.stock_available !== undefined && Number(item.product.stock_available) <= 0);

  useEffect(() => {
    if (!isCartOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') toggleCart(); };
    window.addEventListener('keydown', onKey);
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
    };
  }, [isCartOpen, toggleCart]);

  const handleCheckout = () => {
    const cartShopId = Number(cartItems[0]?.product.shop_id ?? shopId);
    if (!Number.isSafeInteger(cartShopId) || cartShopId <= 0 || cartItems.some((item) => Number(item.product.shop_id) !== cartShopId)) {
      setCartMessage('We could not verify the shop for every item. Remove and re-add the affected item from its shop page.');
      return;
    }
    if (hasUnavailableItems) {
      setCartMessage('Your cart contains an out-of-stock item. Remove it before continuing.');
      return;
    }

    clearCartMessage();
    toggleCart();
    const token = localStorage.getItem('customerToken');

    if (!token) {
      router.push(`/auth?next=${encodeURIComponent(`/shop/${cartShopId}/checkout`)}`);
      return;
    }

    router.push(`/shop/${cartShopId}/checkout`);
  };

  return (
    <AnimatePresence>
      {isCartOpen && (
        <>
          <motion.div
            key="overlay"
            className={styles.overlay}
            onClick={toggleCart}
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          />

          <motion.aside
            key="drawer"
            className={styles.drawer}
            aria-label="Shopping cart"
            role="dialog"
            aria-modal="true"
            initial={{ x: '104%', rotateY: -14 }}
            animate={{ x: 0, rotateY: 0 }}
            exit={{ x: '104%', rotateY: -14 }}
            transition={{ type: 'spring', stiffness: 260, damping: 30 }}
            style={{ transformPerspective: 1600, transformOrigin: 'right center' }}
          >
            <div className={styles.head}>
              <div className={styles.headLeft}>
                <span className={styles.headIcon}><ShoppingBag size={20} /></span>
                <h2>Your cart</h2>
                {count > 0 && <span className={styles.count}>{count}</span>}
              </div>
              <button ref={closeRef} className={styles.close} onClick={toggleCart} aria-label="Close cart">
                <X size={20} />
              </button>
            </div>

            {cartMessage && (
              <div role="alert" style={{ margin: '0 18px 12px', padding: '11px 13px', border: '1px solid #f3b4be', borderRadius: 12, background: '#fff1f2', color: '#9f1239', fontSize: 13, lineHeight: 1.45, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span>{cartMessage}</span>
                <button type="button" onClick={clearCartMessage} aria-label="Dismiss cart message" style={{ alignSelf: 'flex-start', fontWeight: 800 }}>×</button>
              </div>
            )}
            <div className={styles.scroll}>
              {cartItems.length === 0 ? (
                <div className={styles.empty}>
                  <motion.div className={styles.emptyBag} animate={{ y: [0, -12, 0], rotate: [-4, 4, -4] }} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}>
                    <ShoppingBag size={44} strokeWidth={1.5} />
                  </motion.div>
                  <strong>Nothing here yet</strong>
                  <p>Add items from a shop and they&apos;ll show up here.</p>
                  <button className={styles.keep} onClick={toggleCart}>Keep browsing</button>
                </div>
              ) : (
                <ul className={styles.items}>
                  <AnimatePresence initial={false} mode="popLayout">
                    {cartItems.map((item, i) => (
                      <motion.li
                        key={item.product.id}
                        layout
                        className={styles.item}
                        initial={{ opacity: 0, x: 50, scale: 0.96 }}
                        animate={{ opacity: 1, x: 0, scale: 1 }}
                        exit={{ opacity: 0, x: 80, scale: 0.9 }}
                        transition={{ type: 'spring', stiffness: 320, damping: 30, delay: i * 0.04 }}
                      >
                        <div className={styles.thumb}>
                          {item.product.image_url
                            ? <img src={item.product.image_url} alt="" />
                            : <span>{item.product.name.trim().charAt(0).toUpperCase()}</span>}
                        </div>
                        <div className={styles.info}>
                          <div className={styles.name}>{item.product.name}</div>
                          <div className={styles.unit}>₹{Number(item.product.price).toFixed(2)} each</div>
                          <div className={styles.qty}>
                            <button onClick={() => updateQuantity(item.product.id, -1)} aria-label="Decrease quantity"><Minus size={14} /></button>
                            <AnimatePresence mode="popLayout" initial={false}>
                              <motion.span key={item.quantity} initial={{ y: 10, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -10, opacity: 0 }} transition={{ duration: 0.15 }}>
                                {item.quantity}
                              </motion.span>
                            </AnimatePresence>
                            <button onClick={() => updateQuantity(item.product.id, 1)} aria-label="Increase quantity"><Plus size={14} /></button>
                          </div>
                        </div>
                        <div className={styles.side}>
                          <div className={styles.line}>₹{(item.product.price * item.quantity).toFixed(2)}</div>
                          <button className={styles.remove} onClick={() => removeFromCart(item.product.id)} aria-label={`Remove ${item.product.name}`}>
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ul>
              )}
            </div>

            <AnimatePresence>
              {cartItems.length > 0 && (
                <motion.div
                  className={styles.foot}
                  initial={{ y: 40, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 40, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                >
                  <div className={styles.total}>
                    <span>Subtotal</span>
                    <b><Money value={cartTotal} /></b>
                  </div>
                  <p>Estimated subtotal. Final prices, stock and applicable charges are confirmed by the shop at checkout.</p>
                  <button className={styles.checkout} onClick={handleCheckout} id="checkout-btn" disabled={hasUnavailableItems} aria-disabled={hasUnavailableItems} style={hasUnavailableItems ? { opacity: 0.55, cursor: 'not-allowed' } : undefined}>
                    Proceed to checkout <ArrowRight size={18} />
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
