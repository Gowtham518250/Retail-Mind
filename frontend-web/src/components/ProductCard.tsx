'use client';

import Link from 'next/link';
import Image from 'next/image';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import confetti from 'canvas-confetti';
import { Check, Package2, Plus, ShoppingBag } from 'lucide-react';
import { useState } from 'react';
import type { ShopProduct } from '../lib/types';
import { flyProductToCart } from '../lib/cartFlight';
import Tilt3D from './Tilt3D';
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
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
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
    const rect = event.currentTarget.getBoundingClientRect();
    const source = event.currentTarget.closest('article')?.querySelector<HTMLElement>(`.${styles.media}`) || event.currentTarget;
    try {
      if (!reduceMotion) await flyProductToCart(source, product.image_url);
    } catch (error) {
      console.error('Could not animate product into the cart.', error);
    } finally {
      setFlyingToCart(false);
    }
    const added = onAddToCart(product);
    if (!added) return;
    if (!reduceMotion) confetti({
      particleCount: 9,
      spread: 42,
      startVelocity: 13,
      scalar: 0.58,
      ticks: 70,
      gravity: 1.1,
      zIndex: 1200,
      disableForReducedMotion: true,
      colors: ['#e8541e', '#f3ca4f', '#2b4436', '#fbf6ec'],
      origin: { x: (rect.left + rect.width / 2) / window.innerWidth, y: rect.top / window.innerHeight },
    });
  };

  const state = justAdded ? 'added' : inCartCount > 0 ? 'incart' : 'add';

  return (
    <Tilt3D className={styles.wrap} max={2} lift={2}>
      <article className={styles.card}>
        <Link href={href} className={styles.media} aria-label={`View ${product.name}`}>
          {product.image_url && failedImageUrl !== product.image_url ? (
            <Image
              src={product.image_url}
              alt={product.name}
              width={480}
              height={480}
              sizes="(max-width: 640px) 92vw, (max-width: 1000px) 45vw, 300px"
              loading="lazy"
              decoding="async"
              className={styles.image}
              onError={() => setFailedImageUrl(product.image_url || null)}
            />
          ) : (
            <div className={styles.placeholder}>
              <span className={styles.initial} aria-hidden="true">{product.name.trim().charAt(0).toUpperCase()}</span>
              <Package2 size={38} strokeWidth={1.5} />
            </div>
          )}
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

            <motion.button
              type="button"
              className={`${styles.add} ${state === 'added' ? styles.added : ''}`}
              onClick={handleAdd}
              disabled={isOutOfStock || flyingToCart}
              whileTap={reduceMotion ? undefined : { scale: 0.96 }}
              aria-label={`Add ${product.name} to cart`}
            >
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={state}
                  className={styles.addInner}
                  aria-live="polite"
                  aria-atomic="true"
                  initial={{ y: 14, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -14, opacity: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  {isOutOfStock ? 'Unavailable'
                    : flyingToCart ? 'Adding…'
                    : state === 'added' ? <><Check size={16} strokeWidth={3} /> Added</>
                    : state === 'incart' ? <><Plus size={16} strokeWidth={3} /> In cart · {inCartCount}</>
                    : <><ShoppingBag size={16} /> Add</>}
                </motion.span>
              </AnimatePresence>
            </motion.button>
          </div>
        </div>
      </article>
    </Tilt3D>
  );
}
