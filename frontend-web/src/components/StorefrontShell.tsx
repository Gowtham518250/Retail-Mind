'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { Search, SlidersHorizontal, Sparkles, Phone, MapPin, PackageCheck, ShieldCheck, ArrowRight } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { API_BASE } from '../lib/api';
import type { ShopProduct, ShopResponse } from '../lib/types';
import ProductCard from './ProductCard';

interface StorefrontShellProps {
  shopId: number;
}

export default function StorefrontShell({ shopId }: StorefrontShellProps) {
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [shop, setShop] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState<'featured' | 'price-low' | 'price-high' | 'discount'>('featured');
  const [activeCategory, setActiveCategory] = useState('All');
  const [justAddedId, setJustAddedId] = useState<number | null>(null);
  const { addToCart, cartItems } = useCart();

  useEffect(() => {
    const loadShop = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(`${API_BASE}/store/shops/${shopId}/products`);
        if (!res.ok) throw new Error('Unable to load this shop right now.');
        const data = await res.json();
        setShop(data);
        setProducts(data.products || []);
      } catch (err: any) {
        setError(err.message || 'Something went wrong.');
      } finally {
        setLoading(false);
      }
    };

    loadShop();
  }, [shopId]);

  const categories = useMemo(() => {
    const unique = Array.from(new Set(products.map((product) => product.category).filter(Boolean))) as string[];
    return ['All', ...unique];
  }, [products]);

  const filteredProducts = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    let list = [...products];

    if (normalized) {
      list = list.filter((product) => {
        const haystack = `${product.name} ${product.category || ''} ${product.description || ''}`.toLowerCase();
        return haystack.includes(normalized);
      });
    }

    if (activeCategory !== 'All') {
      list = list.filter((product) => product.category === activeCategory);
    }

    switch (sortBy) {
      case 'price-low':
        list.sort((a, b) => a.price - b.price);
        break;
      case 'price-high':
        list.sort((a, b) => b.price - a.price);
        break;
      case 'discount':
        list.sort((a, b) => (b.discount_pct || 0) - (a.discount_pct || 0));
        break;
      default:
        list.sort((a, b) => Number(b.flash_sale_active) - Number(a.flash_sale_active));
        break;
    }

    return list;
  }, [activeCategory, products, search, sortBy]);

  const handleAddToCart = (product: ShopProduct) => {
    addToCart(product);
    setJustAddedId(product.id);
    window.setTimeout(() => setJustAddedId(null), 1200);
  };

  return (
    <div className="store-shell">
      <div className="container">
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
          className="shop-hero-card"
        >
          <div className="shop-hero-copy">
            <div className="hero-pill">Premium local storefront</div>
            <h1>{shop?.shop_name || 'Retail Mind Storefront'}</h1>
            <p>
              {shop?.shop_tagline || 'Discover fresh essentials, daily deals, and a delightful shopping experience built for modern customers.'}
            </p>

            <div className="hero-meta-row">
              {shop?.shop_phone && (
                <div className="hero-meta-pill">
                  <Phone size={16} /> {shop.shop_phone}
                </div>
              )}
              {shop?.shop_address && (
                <div className="hero-meta-pill">
                  <MapPin size={16} /> {shop.shop_address}
                </div>
              )}
            </div>

            <div className="shop-stats-grid">
              <div className="shop-stat-card">
                <PackageCheck size={18} />
                <span>{products.length} products</span>
              </div>
              <div className="shop-stat-card">
                <ShieldCheck size={18} />
                <span>Secure checkout</span>
              </div>
              <div className="shop-stat-card">
                <Sparkles size={18} />
                <span>Fast dispatch</span>
              </div>
            </div>
          </div>

          <div className="shop-hero-panel">
            <div className="hero-panel-card">
              <h2>Live offers</h2>
              <p>Handpicked today’s best picks from this shop.</p>
              <div className="panel-bullets">
                <div><span>•</span> Fresh arrivals</div>
                <div><span>•</span> Express delivery</div>
                <div><span>•</span> Simple reordering</div>
              </div>
              <Link href="#products" className="hero-cta">
                Shop now <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </motion.section>

        <section className="store-toolbar" aria-label="Store controls">
          <label className="store-search-box">
            <Search size={18} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by product, category or keyword"
            />
          </label>

          <div className="store-filter-row">
            <div className="store-filter-group">
              <SlidersHorizontal size={16} />
              <select value={sortBy} onChange={(event) => setSortBy(event.target.value as any)}>
                <option value="featured">Featured</option>
                <option value="price-low">Price: Low to High</option>
                <option value="price-high">Price: High to Low</option>
                <option value="discount">Best discount</option>
              </select>
            </div>
          </div>
        </section>

        <div className="store-category-row">
          {categories.map((category) => (
            <button
              key={category}
              className={`store-category-pill ${activeCategory === category ? 'active' : ''}`}
              onClick={() => setActiveCategory(category)}
            >
              {category}
            </button>
          ))}
        </div>

        <section id="products" className="store-product-section">
          <div className="section-heading">
            <div>
              <p className="section-eyebrow">Curated for you</p>
              <h2>Popular picks</h2>
            </div>
            <div className="section-badge">{filteredProducts.length} items</div>
          </div>

          {loading ? (
            <div className="store-skeleton-grid">
              {Array.from({ length: 6 }).map((_, index) => (
                <div key={index} className="store-skeleton-card" />
              ))}
            </div>
          ) : error ? (
            <div className="store-empty-state">{error}</div>
          ) : filteredProducts.length === 0 ? (
            <div className="store-empty-state">No products match your search yet. Try another keyword.</div>
          ) : (
            <div className="store-product-grid">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  shopId={shopId}
                  inCartCount={cartItems.find((item) => item.product.id === product.id)?.quantity || 0}
                  justAdded={justAddedId === product.id}
                  onAddToCart={handleAddToCart}
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
