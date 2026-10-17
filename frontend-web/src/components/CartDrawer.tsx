'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname, useParams, useRouter } from 'next/navigation';
import Image from 'next/image';
import { AnimatePresence, motion, useSpring, useTransform } from 'framer-motion';
import { ArrowRight, Loader2, Minus, Plus, ShoppingBag, Trash2, X } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './CartDrawer.module.css';

function Money({ value }: { value: number }) {
  const spring = useSpring(value, { stiffness: 150, damping: 22 });
  useEffect(() => { spring.set(value); }, [value, spring]);
  const text = useTransform(spring, (v) => '₹' + v.toFixed(2));
  return <motion.span>{text}</motion.span>;
}

export default function CartDrawer() {
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
  const closeRef = useRef<HTMLButtonElement>(null);
  const [openingCheckout, setOpeningCheckout] = useState(false);
  const count = cartItems.reduce((s, i) => s + i.quantity, 0);

  useEffect(() => {
    setOpeningCheckout(false);
  }, [pathname]);

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
                            ? <Image src={item.product.image_url} alt="" width={74} height={74} sizes="74px" loading="lazy" />
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
                  initial={{ y: 40, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: 40, opacity: 0 }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
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
