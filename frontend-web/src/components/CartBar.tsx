'use client';

import { usePathname } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useCart } from '../context/CartContext';

/** Sticky "N items · ₹total — View cart" bar on shop and product pages. */
export default function CartBar() {
  const pathname = usePathname();
  const { itemCount, cartTotal, toggleCart, isCartOpen } = useCart();
  const reduce = Boolean(useReducedMotion());
  const onShopPage = /^\/shop\/\d+(\/product\/\d+)?\/?$/.test(pathname);
  const show = onShopPage && itemCount > 0 && !isCartOpen;
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className="rm-cartbar"
          role="region"
          aria-label="Cart summary"
          initial={reduce ? false : { y: 40, opacity: 0, x: '-50%' }}
          animate={{ y: 0, opacity: 1, x: '-50%' }}
          exit={reduce ? undefined : { y: 40, opacity: 0, x: '-50%' }}
          transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        >
          <div className="rm-cartbar-text">
            <strong>{itemCount} {itemCount === 1 ? 'item' : 'items'} · ₹{Number(cartTotal).toLocaleString('en-IN', { maximumFractionDigits: 2 })}</strong>
            <span>Delivery and coupons at checkout</span>
          </div>
          <button type="button" onClick={toggleCart}>View cart</button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
