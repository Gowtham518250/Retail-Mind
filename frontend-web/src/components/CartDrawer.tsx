'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { AnimatePresence, motion, useReducedMotion, useSpring, useTransform } from 'framer-motion';
import { ArrowRight, Loader2, Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './CartDrawer.module.css';

function Money({ value }: { value: number }) {
  const reduceMotion = Boolean(useReducedMotion());
  const spring = useSpring(value, reduceMotion ? { stiffness: 1200, damping: 90 } : { stiffness: 150, damping: 22 });
  useEffect(() => { spring.set(value); }, [value, spring]);
  const text = useTransform(spring, (v) => '₹' + v.toFixed(2));
  return <motion.span>{text}</motion.span>;
}

export default function CartDrawer() {
  const reduceMotion = Boolean(useReducedMotion());
  const {
    cartItems,
    isCartOpen,
    cartNotice,
    canReplaceCart,
    toggleCart,
    updateQuantity,
    removeFromCart,
    replaceCartWithPendingProduct,
    dismissCartNotice,
    cartTotal,
  } = useCart();
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  const shopId = Number(params?.shopId || 8);
  const drawerRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [openingCheckout, setOpeningCheckout] = useState(false);
  const count = cartItems.reduce((s, i) => s + i.quantity, 0);

  useEffect(() => {
    setOpeningCheckout(false);
  }, [pathname]);

  const toggleCartRef = useRef(toggleCart);
  useEffect(() => { toggleCartRef.current = toggleCart; }, [toggleCart]);

  useEffect(() => {
    if (!isCartOpen) return;
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        toggleCartRef.current();
        return;
      }
      if (e.key !== 'Tab') return;
      const focusables = Array.from(drawerRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ) || []).filter((element) => element.offsetParent !== null);
      if (!focusables.length) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', onKey);
    closeRef.current?.focus();
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener('keydown', onKey);
      previousFocusRef.current?.focus();
    };
  }, [isCartOpen]);

  const handleCheckout = () => {
    const cartShopId = cartItems[0]?.product.shop_id || shopId;
    const token = localStorage.getItem('customerToken');
    const destination = token
      ? `/shop/${cartShopId}/checkout`
      : `/auth?next=${encodeURIComponent(`/shop/${cartShopId}/checkout`)}`;

    toggleCart();
    if (pathname === destination.split('?')[0]) return;
    setOpeningCheckout(true);
    router.push(destination);
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
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            transition={reduceMotion ? { duration: 0 } : { duration: 0.24 }}
          />

          <motion.aside
            key="drawer"
            ref={drawerRef}
            className={styles.drawer}
            aria-labelledby="cart-drawer-title"
            role="dialog"
            aria-modal="true"
            initial={reduceMotion ? false : { x: '100%' }}
            animate={{ x: 0 }}
            exit={reduceMotion ? undefined : { x: '100%' }}
            transition={reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 300, damping: 32 }}
          >
            <div className={styles.head}>
              <div className={styles.headLeft}>
                <span className={styles.headIcon}><ShoppingBag size={20} /></span>
                <h2 id="cart-drawer-title">Your cart</h2>
                {count > 0 && <span className={styles.count}>{count}</span>}
              </div>
              <button ref={closeRef} className={styles.close} onClick={toggleCart} aria-label="Close cart">
                <X size={20} />
              </button>
            </div>

            <div className={styles.scroll}>
              {cartNotice && (
                <div className={styles.notice} role="alert">
                  <p>{cartNotice}</p>
                  <div className={styles.noticeActions}>
                    {canReplaceCart && (
                      <button
                        type="button"
                        className={styles.noticePrimary}
                        onClick={replaceCartWithPendingProduct}
                      >
                        Replace cart with this item
                      </button>
                    )}
                    <button type="button" onClick={dismissCartNotice}>
                      Dismiss
                    </button>
                  </div>
                </div>
              )}
              {cartItems.length === 0 ? (
                <div className={styles.empty}>
                  <div className={styles.emptyBag}>
                    <ShoppingBag size={44} strokeWidth={1.5} />
                  </div>
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
                        initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={reduceMotion ? undefined : { opacity: 0 }}
                        transition={reduceMotion ? { duration: 0 } : { duration: 0.18, delay: i * 0.02 }}
                      >
                        <div className={styles.thumb}>
                          {item.product.image_url
                            ? <Image src={item.product.image_url} alt="" width={74} height={74} sizes="74px" loading="lazy" />
                            : <span>{item.product.name.trim().charAt(0).toUpperCase()}</span>}
                        </div>
                        <div className={styles.info}>
                          <div className={styles.name}>{item.product.name}</div>
                          <div className={styles.unit}>₹{Number(item.product.price).toFixed(2)} each</div>
                          <div className={styles.qty}>
                            <button onClick={() => updateQuantity(item.product.id, -1)} aria-label="Decrease quantity"><Minus size={14} /></button>
                            <AnimatePresence mode="popLayout" initial={false}>
                              <motion.span key={item.quantity} initial={reduceMotion ? false : { y: 6, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={reduceMotion ? undefined : { y: -6, opacity: 0 }} transition={reduceMotion ? { duration: 0 } : { duration: 0.13 }}>
                                {item.quantity}
                              </motion.span>
                            </AnimatePresence>
                            <button
                              onClick={() => updateQuantity(item.product.id, 1)}
                              disabled={item.product.stock_available !== undefined && item.quantity >= item.product.stock_available}
                              aria-label={`Increase ${item.product.name} quantity`}
                            >
                              <Plus size={14} />
                            </button>
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
                  initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={reduceMotion ? undefined : { opacity: 0 }}
                  transition={reduceMotion ? { duration: 0 } : { duration: 0.18 }}
                >
                  <div className={styles.total}>
                    <span>Subtotal</span>
                    <b><Money value={cartTotal} /></b>
                  </div>
                  <p>Taxes included. Delivery charges calculated at checkout.</p>
                  <button
                    className={styles.checkout}
                    onClick={handleCheckout}
                    disabled={openingCheckout}
                    aria-busy={openingCheckout}
                    id="checkout-btn"
                  >
                    {openingCheckout
                      ? <><Loader2 size={18} className="spin" /> Opening checkout…</>
                      : <>Proceed to checkout <ArrowRight size={18} /></>}
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
