'use client';

import Link from 'next/link';
import { motion } from 'framer-motion';
import { ShoppingCart, Sparkles, Package2 } from 'lucide-react';
import type { ShopProduct } from '../lib/types';
import { useLanguage } from '../context/LanguageContext';

interface ProductCardProps {
  product: ShopProduct;
  shopId: number;
  inCartCount: number;
  justAdded: boolean;
  onAddToCart: (product: ShopProduct) => void;
}

export default function ProductCard({
  product,
  shopId,
  inCartCount,
  justAdded,
  onAddToCart,
}: ProductCardProps) {
  const { t } = useLanguage();
  const discount = product.original_price && product.original_price > product.price
    ? Math.round(((product.original_price - product.price) / product.original_price) * 100)
    : product.discount_pct || 0;

  const isOutOfStock = (product.stock_available ?? 0) <= 0;

  return (
    <motion.article
      whileHover={{ y: -6, scale: 1.01 }}
      transition={{ type: 'spring', stiffness: 260, damping: 20 }}
      className="store-product-card"
    >
      <div className="store-product-media">
        {product.image_url ? (
          <img src={product.image_url} alt={product.name} loading="lazy" className="store-product-image" />
        ) : (
          <div className="store-product-placeholder">
            <Package2 size={40} />
          </div>
        )}

        {discount > 0 && (
          <span className="store-badge discount">{discount}% {t('product_off')}</span>
        )}
        {isOutOfStock ? (
          <span className="store-badge sold-out">{t('product_out')}</span>
        ) : (
          <span className="store-badge stock">{t('product_in')}</span>
        )}
      </div>

      <div className="store-product-body">
        <div className="store-product-topline">
          <span className="store-category-pill">{product.category || t('product_featured')}</span>
          <span className="store-rating-pill"><Sparkles size={12} /> 4.8</span>
        </div>

        <h3 className="store-product-title">{product.name}</h3>
        <p className="store-product-desc">{product.description || t('product_desc')}</p>

        <div className="store-price-row">
          <div>
            <div className="store-price">₹{product.price.toFixed(2)}</div>
            {product.original_price && product.original_price > product.price && (
              <div className="store-original-price">₹{product.original_price.toFixed(2)}</div>
            )}
          </div>
          <div className="store-stock-text">
            {product.stock_available !== undefined ? `${product.stock_available} {t('product_left')}` : t('product_ready')}
          </div>
        </div>

        <div className="store-card-actions">
          <button
            className="store-cart-btn"
            onClick={() => onAddToCart(product)}
            disabled={isOutOfStock}
          >
            <ShoppingCart size={16} />
            {justAdded ? t('product_added') : inCartCount > 0 ? `${t('product_in_cart')} ×${inCartCount}` : t('product_add')}
          </button>
          <Link href={`/shop/${shopId}/product/${product.id}`} className="store-link-btn">
            View
          </Link>
        </div>
      </div>
    </motion.article>
  );
}
