'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, ShoppingCart, Sparkles, Package2, Truck, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { API_BASE } from '../../../../../lib/api';
import { useCart } from '../../../../../context/CartContext';
import type { ShopProduct } from '../../../../../lib/types';

export default function ProductClientPage() {
  const params = useParams();
  const shopId = Number(params?.shopId || 8);
  const productId = Number(params?.productId);
  const { addToCart } = useCart();
  const [product, setProduct] = useState<ShopProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [added, setAdded] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await fetch(API_BASE + '/store/shops/' + shopId + '/products');
        if (!res.ok) throw new Error('Unable to load product');
        const data = await res.json();
        setProduct(data.products?.find((item: ShopProduct) => item.id === productId) || null);
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

  if (loading) return <div className="page-loading">Loading product details…</div>;
  if (!product) return <div className="container product-page"><div className="store-empty-state">This product is not available right now.</div></div>;

  const stockAvailable = product.stock_available ?? 0;

  const handleAdd = () => {
    addToCart({ ...product, shop_id: shopId });
    setAdded(true);
    window.setTimeout(() => setAdded(false), 1300);
  };

  return (
    <main className="container product-page">
      <Link href={'/shop/' + shopId} className="product-back"><ArrowLeft size={16} /> Back to shop</Link>
      <motion.section className="product-detail" initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .45 }}>
        <div className="product-visual">
          <div className="product-glow" />
          <motion.div className="product-orbit" animate={{ rotate: 360 }} transition={{ duration: 22, repeat: Infinity, ease: 'linear' }}>
            <span /><span /><span />
          </motion.div>
          <motion.div className="product-image-frame" animate={{ y: [0, -6, 0], rotateZ: [-1, 1, -1] }} transition={{ duration: 5.2, repeat: Infinity, ease: 'easeInOut' }}>
            {product.image_url ? <img src={product.image_url} alt={product.name} /> : <Package2 size={70} />}
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
            <span className={stockAvailable > 0 ? 'available' : 'unavailable'}>
              {stockAvailable > 0 ? String(stockAvailable) + ' available' : 'Out of stock'}
            </span>
            <span>Shop #{shopId}</span>
          </div>

          <div className="product-actions">
            <button className="store-cart-btn" onClick={handleAdd} disabled={stockAvailable <= 0}>
              <ShoppingCart size={17} /> {added ? 'Added to cart' : 'Add to cart'}
            </button>
            <Link href="/orders" className="store-link-btn">View orders</Link>
          </div>
        </div>
      </motion.section>
    </main>
  );
}
