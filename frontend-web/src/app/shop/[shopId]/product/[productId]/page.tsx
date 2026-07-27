'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ShoppingCart, Sparkles, Package2, Truck, ShieldCheck } from 'lucide-react';
import { API_BASE } from '../../../../../lib/api';
import { useCart } from '../../../../../context/CartContext';
import type { ShopProduct } from '../../../../../lib/types';

export default function ProductDetailPage() {
  const params = useParams();
  const shopId = Number(params?.shopId || 8);
  const productId = Number(params?.productId);
  const { addToCart } = useCart();
  const [product, setProduct] = useState<ShopProduct | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/store/shops/${shopId}/products`);
        if (!res.ok) throw new Error('Unable to load product');
        const data = await res.json();
        const matched = data.products?.find((item: ShopProduct) => item.id === productId) || null;
        setProduct(matched);
      } catch {
        setProduct(null);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [productId, shopId]);

  const discount = useMemo(() => {
    if (!product) return 0;
    if (product.original_price && product.original_price > product.price) {
      return Math.round(((product.original_price - product.price) / product.original_price) * 100);
    }
    return product.discount_pct || 0;
  }, [product]);

  if (loading) {
    return <div className="container" style={{ padding: '40px 20px' }}><div className="store-empty-state">Loading product…</div></div>;
  }

  if (!product) {
    return <div className="container" style={{ padding: '40px 20px' }}><div className="store-empty-state">This product is not available right now.</div></div>;
  }

  return (
    <div className="container" style={{ padding: '28px 20px 80px' }}>
      <Link href={`/${shopId ? `?shop_id=${shopId}` : ''}`} className="hero-cta" style={{ width: 'fit-content', marginBottom: 20 }}>
        <ArrowLeft size={16} /> Back to shop
      </Link>
      <div className="shop-hero-card" style={{ gridTemplateColumns: '1fr 0.9fr' }}>
        <div className="store-product-media" style={{ borderRadius: 24, overflow: 'hidden' }}>
          {product.image_url ? (
            <img src={product.image_url} alt={product.name} className="store-product-image" />
          ) : (
            <div className="store-product-placeholder"><Package2 size={48} /></div>
          )}
        </div>
        <div>
          <div className="hero-pill">{product.category || 'Featured'}</div>
          <h1 style={{ margin: '14px 0 10px', fontSize: '34px' }}>{product.name}</h1>
          <p style={{ color: 'rgba(255,255,255,0.68)', lineHeight: 1.7 }}>{product.description || 'A well-curated product chosen for daily convenience and quality.'}</p>
          <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
            <div className="store-price">₹{product.price.toFixed(2)}</div>
            {product.original_price && product.original_price > product.price && <div className="store-original-price">₹{product.original_price.toFixed(2)}</div>}
          </div>
          {discount > 0 && <div className="hero-meta-pill" style={{ marginTop: 12, width: 'fit-content' }}>{discount}% off today</div>}
          <div className="shop-stats-grid" style={{ marginTop: 18 }}>
            <div className="shop-stat-card"><Truck size={16} /> Fast delivery</div>
            <div className="shop-stat-card"><ShieldCheck size={16} /> Secure checkout</div>
            <div className="shop-stat-card"><Sparkles size={16} /> Premium quality</div>
          </div>
          <div className="store-card-actions" style={{ marginTop: 22 }}>
            <button className="store-cart-btn" onClick={() => addToCart(product)}>
              <ShoppingCart size={16} /> Add to cart
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
