'use client';

import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { Check, Minus, Plus } from 'lucide-react';
import { useCallback, useRef } from 'react';
import { useState } from 'react';
import type { ShopProduct } from '../lib/types';
import { flyProductToCart } from '../lib/cartFlight';
import ProductImage from './ProductImage';
import { useCart } from '../context/CartContext';
import styles from './ProductCard.module.css';

interface ProductCardProps {
  product: ShopProduct;
  shopId: number;
  inCartCount: number;
  justAdded: boolean;
  onAddToCart: (product: ShopProduct) => boolean;
}

export default function ProductCard({ product, shopId, inCartCount, justAdded, onAddToCart }: ProductCardProps) {
  const reduceMotion = Boolean(useReducedMotion());
  const { updateQuantity } = useCart();
  const shownImage = useRef<string | null>(null);
  const onResolved = useCallback((url: string | null) => { shownImage.current = url; }, []);
  const [flyingToCart, setFlyingToCart] = useState(false);
  const discount = product.original_price && product.original_price > product.price
    ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
    : product.discount_pct || 0;

  const stock = product.stock_available;
  const isOutOfStock = stock !== undefined && stock <= 0;
  const lowStock = !isOutOfStock && stock !== undefined && stock <= 5;
  const href = `/shop/${shopId}/product/${product.id}`;

  const handleAdd = async (event: React.MouseEvent<HTMLButtonElement>) => {
    if (flyingToCart) return;
    setFlyingToCart(true);
    const source = event.currentTarget.closest('article')?.querySelector<HTMLElement>(`.${styles.media}`) || event.currentTarget;
    try {
      if (!reduceMotion) await flyProductToCart(source, shownImage.current || undefined);
    } catch (error) {
      console.error('Could not animate product into the cart.', error);
    } finally {
      setFlyingToCart(false);
    }
    const added = onAddToCart(product);
    if (!added) return;

  };

  return (
    <div className={styles.wrap}>
      <article className={styles.card}>
        <Link href={href} className={styles.media} aria-label={`View ${product.name}`}>
          <ProductImage src={product.image_url} name={product.name} category={product.category} onResolved={onResolved} />
          <div className={styles.badges}>
            {discount > 0 && <span className={`${styles.badge} ${styles.sale}`}>{discount}% off</span>}
            {isOutOfStock && <span className={`${styles.badge} ${styles.out}`}>Sold out</span>}
            {lowStock && <span className={`${styles.badge} ${styles.low}`}>Only {stock} left</span>}
          </div>
        </Link>

        <div className={styles.body}>
          <span className={styles.category}>{product.category || 'Featured'}</span>
          <h3 className={styles.title}><Link href={href}>{product.name}</Link></h3>
          <p className={styles.desc}>{product.description || 'Freshly curated for your daily essentials.'}</p>

          <div className={styles.buy}>
            <div className={styles.priceBox}>
              <div className={styles.price}>₹{product.price.toFixed(2)}</div>
              {product.original_price && product.original_price > product.price && (
                <div className={styles.was}>₹{product.original_price.toFixed(2)}</div>
              )}
            </div>

            {inCartCount > 0 && !justAdded ? (
              <div className={styles.stepper} role="group" aria-label={`Quantity of ${product.name} in cart`}>
                <button type="button" onClick={() => updateQuantity(product.id, -1)} aria-label={`Remove one ${product.name}`}><Minus size={16} strokeWidth={3} /></button>
                <output aria-live="polite">{inCartCount}</output>
                <button
                  type="button"
                  onClick={() => updateQuantity(product.id, 1)}
                  disabled={stock !== undefined && inCartCount >= stock}
                  aria-label={`Add one more ${product.name}`}
                ><Plus size={16} strokeWidth={3} /></button>
              </div>
            ) : (
              <motion.button
                type="button"
                className={`${styles.add} ${justAdded ? styles.added : ''}`}
                onClick={handleAdd}
                disabled={isOutOfStock || flyingToCart}
                whileTap={reduceMotion ? undefined : { scale: 0.96 }}
                aria-label={`Add ${product.name} to cart`}
              >
                {isOutOfStock ? 'Sold out'
                  : flyingToCart ? 'Adding…'
                  : justAdded ? <><Check size={16} strokeWidth={3} /> Added</>
                  : <><Plus size={16} strokeWidth={3} /> Add</>}
              </motion.button>
            )}
          </div>
        </div>
      </article>
    </div>
  );
}
