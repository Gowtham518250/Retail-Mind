'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { ShoppingCart, Star, Package, Search } from 'lucide-react';
import { useCart, Product } from '../context/CartContext';
import { API_BASE } from '../lib/api';

const SHOP_ID = 1;

export default function Home() {
  const [products, setProducts]     = useState<Product[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [search, setSearch]         = useState('');
  const [addedId, setAddedId]       = useState<number | null>(null);
  const router = useRouter();
  const { addToCart, cartItems } = useCart();

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('customerToken') : null;
    if (!token) { router.replace('/auth'); return; }

    const fetchProducts = async () => {
      try {
        const res = await fetch(`${API_BASE}/store/shops/${SHOP_ID}/products`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem('customerToken');
          localStorage.removeItem('customerName');
          router.replace('/auth');
          return;
        }
        if (!res.ok) throw new Error('Failed to load products');
        const data = await res.json();
        setProducts(data.products || []);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchProducts();
  }, [router]);

  const filtered = useMemo(() =>
    products.filter(p =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.category || '').toLowerCase().includes(search.toLowerCase())
    ),
    [products, search]
  );

  const handleAddToCart = (product: Product) => {
    addToCart(product);
    setAddedId(product.id);
    setTimeout(() => setAddedId(null), 1200);
  };

  return (
    <div>
      {/* Hero Banner */}
      <section className="hero-banner">
        <div className="hero-content container">
          <div className="hero-badge">🛍️ New Arrivals Every Day</div>
          <h1 className="hero-title">Shop the Best,<br />At Your Doorstep</h1>
          <p className="hero-sub">Discover hand-picked products from your trusted local store.</p>
        </div>
        <div className="hero-gradient-ring" />
      </section>

      {/* Search bar */}
      <div className="container">
        <div className="search-container">
          <Search size={18} className="search-icon" />
          <input
            type="text"
            className="search-input"
            placeholder="Search products by name or category..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Stats strip */}
        {!loading && !error && (
          <div className="stats-strip">
            <span><Package size={14} style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />{filtered.length} products</span>
            <span><Star size={14} style={{ display:'inline', verticalAlign:'middle', marginRight:4 }} />Top quality</span>
            <span>🚚 Fast delivery</span>
          </div>
        )}

        {/* Product grid */}
        <section className="product-grid" aria-label="Product listing">
          {loading ? (
            Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="product-card skeleton-card">
                <div className="skeleton-img" />
                <div className="skeleton-line short" />
                <div className="skeleton-line" />
                <div className="skeleton-line shorter" />
              </div>
            ))
          ) : error ? (
            <div className="state-message error-state" style={{ gridColumn: '1 / -1' }}>
              ⚠️ {error}
            </div>
          ) : filtered.length === 0 ? (
            <div className="state-message" style={{ gridColumn: '1 / -1' }}>
              <Package size={48} style={{ opacity: 0.3, marginBottom: 12 }} />
              <h3>No products found</h3>
              <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>Try a different search</p>
            </div>
          ) : (
            filtered.map(product => {
              const inCart = cartItems.find(item => item.product.id === product.id);
              const justAdded = addedId === product.id;
              return (
                <div key={product.id} className={`product-card hover-card ${justAdded ? 'just-added' : ''}`}>
                  {/* Image */}
                  <div className="product-img-wrap">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="product-img" />
                    ) : (
                      <div className="product-img-placeholder">
                        <Package size={40} style={{ opacity: 0.3 }} />
                      </div>
                    )}
                    {product.stock_available !== undefined && product.stock_available <= 5 && product.stock_available > 0 && (
                      <div className="stock-badge">Only {product.stock_available} left</div>
                    )}
                    {product.stock_available === 0 && (
                      <div className="stock-badge out">Out of Stock</div>
                    )}
                  </div>

                  {/* Info */}
                  <div className="product-info">
                    {product.category && (
                      <span className="product-category">{product.category}</span>
                    )}
                    <h3 className="product-title">{product.name}</h3>
                    <div className="product-price-row">
                      <span className="product-price">₹{Number(product.price).toFixed(2)}</span>
                    </div>
                  </div>

                  {/* CTA */}
                  <button
                    className={`add-cart-btn ${inCart ? 'in-cart' : ''}`}
                    onClick={() => handleAddToCart(product)}
                    disabled={product.stock_available === 0}
                  >
                    <ShoppingCart size={16} />
                    {justAdded ? '✓ Added!' : inCart ? `In Cart (${inCart.quantity})` : 'Add to Cart'}
                  </button>
                </div>
              );
            })
          )}
        </section>
      </div>
    </div>
  );
}
