'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ShoppingCart, Sparkles, Package2, Truck, ShieldCheck, CheckCircle2, Star, Minus, Plus } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import { API_BASE } from '../../../../../lib/api';
import { useCart } from '../../../../../context/CartContext';
import type { ShopProduct } from '../../../../../lib/types';
import JsonLd from '../../../../../components/JsonLd';
import { absoluteSiteUrl, publicImageUrl } from '../../../../../lib/seo';

export default function ProductClientPage({
  shopId,
  productId,
  initialProduct,
  shopName,
}: {
  shopId: number;
  productId: number;
  initialProduct: ShopProduct | null;
  shopName: string;
}) {
  const shouldReduceMotion = Boolean(useReducedMotion());
  const { addToCart } = useCart();
  const [product, setProduct] = useState<ShopProduct | null>(initialProduct);
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(!initialProduct);
  const [loadError, setLoadError] = useState('');
  const [reloadCount, setReloadCount] = useState(0);
  const [added, setAdded] = useState(false);
  const [quantity, setQuantity] = useState(1);
  const [reviews, setReviews] = useState<
    Array<{ id: number; customer_name: string; rating: number; comment?: string | null; created_at?: string | null }>
  >([]);

  useEffect(() => {
    setQuantity(1);
    setAdded(false);
    const controller = new AbortController();
    let cancelled = false;
    const load = async () => {
      if (initialProduct) {
        setProduct(initialProduct);
        setLoading(false);
        try {
          const reviewResponse = await fetch(
            API_BASE + '/store/shops/' + shopId + '/reviews?limit=12',
            { cache: 'no-store', signal: controller.signal },
          );
          if (reviewResponse.ok) {
            const reviewData = await reviewResponse.json();
            if (!cancelled) setReviews(Array.isArray(reviewData.reviews) ? reviewData.reviews : []);
          }
        } catch {
          if (!cancelled) setReviews([]);
        }
        return;
      }
      setLoading(true);
      setLoadError('');
      try {
        const res = await fetch(API_BASE + '/store/shops/' + shopId + '/products', {
          signal: controller.signal,
        });
        if (!res.ok) throw new Error('Unable to load this product right now.');
        const data = await res.json();
        const foundProduct = data.products?.find((item: ShopProduct) => item.id === productId) || null;
        if (cancelled) return;
        setProduct(foundProduct);
        if (!foundProduct) setLoadError('This product is not available in this shop right now.');

        try {
          const reviewResponse = await fetch(
            API_BASE + '/store/shops/' + shopId + '/reviews?limit=12',
            { cache: 'no-store', signal: controller.signal },
          );
          if (reviewResponse.ok) {
            const reviewData = await reviewResponse.json();
            if (!cancelled) setReviews(Array.isArray(reviewData.reviews) ? reviewData.reviews : []);
          }
        } catch {
          if (!cancelled) setReviews([]);
        }
      } catch (error) {
        if (cancelled) return;
        setProduct(null);
        setLoadError(error instanceof TypeError
          ? 'We couldn’t reach this shop. Check your connection and try again.'
          : error instanceof Error
            ? error.message
            : 'Unable to load this product right now.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [initialProduct, productId, reloadCount, shopId]);

  const discount = useMemo(() => {
    if (!product) return 0;
    if (product.original_price && product.original_price > product.price) {
      return Math.round(((product.original_price - product.price) / product.original_price) * 100);
    }
    return product.discount_pct || 0;
  }, [product]);

  if (loading) return <div className="page-loading" data-experience="product">Loading product details…</div>;
  if (!product) {
    return (
      <div className="container product-page" data-experience="product">
        <div className="store-empty-state" role="alert">
          <p>{loadError || 'This product is not available right now.'}</p>
          <div className="product-recovery-actions">
            <button type="button" className="hero-cta" onClick={() => setReloadCount((count) => count + 1)}>
              Try again
            </button>
            <Link href={`/shop/${shopId}`} className="store-link-btn">Back to shop</Link>
          </div>
        </div>
      </div>
    );
  }

  const stockAvailable = product.stock_available;
  const isOutOfStock = stockAvailable !== undefined && stockAvailable <= 0;
  const maxQuantity = stockAvailable === undefined ? 99 : Math.max(0, stockAvailable);

  const handleAdd = () => {
    if (isOutOfStock) return;
    if (!addToCart({ ...product, shop_id: shopId }, quantity)) return;
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1300);
  };

  return (
    <main className="container product-page" data-experience="product">
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
          { '@type': 'ListItem', position: 2, name: shopName, item: absoluteSiteUrl(`/shop/${shopId}`) },
          { '@type': 'ListItem', position: 3, name: product.name, item: absoluteSiteUrl(`/shop/${shopId}/product/${product.id}`) },
        ],
      }} />
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'Product',
        name: product.name,
        description: product.description || undefined,
        image: [publicImageUrl(product.image_url)],
        sku: String(product.id),
        offers: {
          '@type': 'Offer',
          priceCurrency: 'INR',
          price: Number(product.price).toFixed(2),
          availability: product.stock_available === undefined || product.stock_available > 0
            ? 'https://schema.org/InStock'
            : 'https://schema.org/OutOfStock',
          url: absoluteSiteUrl(`/shop/${shopId}/product/${product.id}`),
          seller: { '@type': 'Organization', name: shopName },
        },
      }} />
      <nav aria-label="Breadcrumb" className="product-back">
        <Link href="/">Marketplace</Link>
        <span aria-hidden="true"> / </span>
        <Link href={`/shop/${shopId}`}>{shopName}</Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{product.name}</span>
      </nav>
      <motion.section className="product-detail" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45 }}>
        <div className="product-visual">
          <div className="product-glow" />
          <motion.div className="product-orbit" animate={shouldReduceMotion ? { rotate: 0 } : { rotate: 360 }} transition={shouldReduceMotion ? { duration: 0 } : { duration: 22, repeat: Infinity, ease: 'linear' }}>
            <span /><span /><span />
          </motion.div>
          <motion.div className="product-image-frame" animate={shouldReduceMotion ? { y: 0, rotateZ: 0 } : { y: [0, -9, 0], rotateZ: [-1, 1, -1] }} transition={shouldReduceMotion ? { duration: 0 } : { duration: 5.2, repeat: Infinity, ease: 'easeInOut' }}>
            {product.image_url && failedImageUrl !== product.image_url
              ? <img
                  src={product.image_url}
                  alt={product.name}
                  width={720}
                  height={720}
                  loading="eager"
                  fetchPriority="high"
                  decoding="async"
                  onError={() => setFailedImageUrl(product.image_url || null)}
                />
              : <Package2 size={70} />}
          </motion.div>
          <div className="product-floating-badge"><CheckCircle2 size={15} /> Local stock</div>
        </div>

        <div className="product-copy">
          <span className="store-category-pill">{product.category || 'Featured'}</span>
          <h1>{product.name}</h1>
          <p>{product.description || 'A carefully selected everyday essential, available from your local shop.'}</p>

          <div className="product-price-row">
            <div className="product-main-price">₹{product.price.toFixed(2)}</div>
            {product.original_price && product.original_price > product.price && <div className="store-original-price">₹{product.original_price.toFixed(2)}</div>}
            {discount > 0 && <span className="product-save-pill">Save {discount}%</span>}
          </div>

          <div className="product-benefits">
            <div><Truck size={16} /><span>Fast delivery</span></div>
            <div><ShieldCheck size={16} /><span>Secure checkout</span></div>
            <div><Sparkles size={16} /><span>Retail Mind verified</span></div>
          </div>

          <div className="product-availability">
            <span className={isOutOfStock ? 'unavailable' : 'available'}>
              {isOutOfStock
                ? 'Out of stock'
                : stockAvailable === undefined
                  ? 'Availability confirmed by shop'
                  : `${stockAvailable} available`}
            </span>
            <span>Shop #{shopId}</span>
          </div>

          {!isOutOfStock && (
            <div className="product-quantity-row">
              <span>Quantity</span>
              <div className="product-quantity-control">
                <button
                  type="button"
                  onClick={() => setQuantity((current) => Math.max(1, current - 1))}
                  disabled={quantity <= 1}
                  aria-label="Decrease quantity"
                >
                  <Minus size={16} />
                </button>
                <output aria-live="polite">{quantity}</output>
                <button
                  type="button"
                  onClick={() => setQuantity((current) => Math.min(maxQuantity, current + 1))}
                  disabled={quantity >= maxQuantity}
                  aria-label="Increase quantity"
                >
                  <Plus size={16} />
                </button>
              </div>
            </div>
          )}

          <div className="product-actions">
            <button className="store-cart-btn" onClick={handleAdd} disabled={isOutOfStock}>
              <ShoppingCart size={17} /> {isOutOfStock ? 'Unavailable' : added ? `Added ${quantity} to cart` : 'Add to cart'}
            </button>
            <Link href="/orders" className="store-link-btn">View orders</Link>
          </div>
        </div>
      </motion.section>

      <motion.section
        className="product-reviews-panel"
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.2 }}
        transition={{ duration: .45 }}
      >
        <div className="product-reviews-head">
          <div>
            <span className="store-category-pill">Verified customer voice</span>
            <h2>What shoppers say</h2>
            <p>Reviews are tied to completed orders from this shop.</p>
          </div>
          <div className="product-reviews-summary">
            <strong>{reviews.length ? (reviews.reduce((sum, item) => sum + Number(item.rating || 0), 0) / reviews.length).toFixed(1) : '—'}</strong>
            <span>/ 5 average</span>
          </div>
        </div>

        {reviews.length === 0 ? (
          <div className="product-review-empty">
            <Sparkles size={18} />
            No verified reviews yet. Your completed order can be the first voice here.
          </div>
        ) : (
          <div className="product-reviews-grid">
            {reviews.map((review) => (
              <article key={review.id} className="product-review-card">
                <div className="product-review-top">
                  <strong>{review.customer_name || 'Customer'}</strong>
                  <span>{review.created_at ? new Date(review.created_at).toLocaleDateString('en-IN') : ''}</span>
                </div>
                <div className="product-review-stars">
                  {Array.from({ length: 5 }, (_, index) => (
                    <Star
                      key={index}
                      size={14}
                      fill={index < Number(review.rating || 0) ? 'currentColor' : 'none'}
                    />
                  ))}
                </div>
                {review.comment && <p>“{review.comment}”</p>}
              </article>
            ))}
          </div>
        )}
      </motion.section>
      {!isOutOfStock && (
        <div className="product-mobile-buy" aria-label="Quick add to cart">
          <div className="product-mobile-quantity">
            <button
              type="button"
              onClick={() => setQuantity((current) => Math.max(1, current - 1))}
              disabled={quantity <= 1}
              aria-label="Decrease quantity"
            >
              <Minus size={16} />
            </button>
            <output aria-live="polite">{quantity}</output>
            <button
              type="button"
              onClick={() => setQuantity((current) => Math.min(maxQuantity, current + 1))}
              disabled={quantity >= maxQuantity}
              aria-label="Increase quantity"
            >
              <Plus size={16} />
            </button>
          </div>
          <div className="product-mobile-total">
            <span>Total</span>
            <strong>₹{(product.price * quantity).toFixed(2)}</strong>
          </div>
          <button type="button" className="store-cart-btn" onClick={handleAdd}>
            <ShoppingCart size={17} /> {added ? 'Added' : 'Add'}
          </button>
        </div>
      )}
    </main>
  );
}
