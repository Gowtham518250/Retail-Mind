'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

interface Product {
  id: string | number;
  name: string;
  price: number;
  image_url?: string;
  category?: string;
  stock?: number;
}

export default function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const router = useRouter();
  
  // Defaulting to shop_id = 1 as per original implementation fallback
  const SHOP_ID = 1;

  useEffect(() => {
    // 1. Check Auth State
    const token = localStorage.getItem('customerToken');
    if (!token) {
      // Redirect to Auth Gate
      router.push('/auth');
      return;
    }

    // 2. Fetch Products for this specific owner's shop
    const fetchProducts = async () => {
      try {
        const response = await fetch(`/store/shops/${SHOP_ID}/products`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        
        if (!response.ok) {
          // If unauthorized, token might be expired
          if (response.status === 401 || response.status === 403) {
            localStorage.removeItem('customerToken');
            localStorage.removeItem('customerName');
            router.push('/auth');
            return;
          }
          throw new Error('Failed to load products');
        }

        const data = await response.json();
        setProducts(data);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchProducts();
  }, [router]);

  // If loading or error, we might still show skeleton or message
  return (
    <div className="container">
      <section className="hero">
        <h1>Welcome to RetailShop</h1>
        <p>Discover the best products at unbeatable prices.</p>
      </section>

      <section>
        <div className="product-grid">
          {loading ? (
            // Skeleton loaders
            Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="product-card hover-card">
                <div className="product-image-skeleton"></div>
                <div style={{ height: '20px', background: '#eee', borderRadius: '4px', width: '80%' }}></div>
                <div style={{ height: '24px', background: '#eee', borderRadius: '4px', width: '40%' }}></div>
              </div>
            ))
          ) : error ? (
            <div style={{ color: 'red', padding: '20px' }}>{error}</div>
          ) : products.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', gridColumn: '1 / -1' }}>
              <h3>No products found for this shop.</h3>
            </div>
          ) : (
            products.map((product) => (
              <div key={product.id} className="product-card hover-card">
                <div className="product-image-skeleton" style={{ background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
                   {product.image_url ? (
                     <img src={product.image_url} alt={product.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                   ) : (
                     <span style={{ fontSize: '48px' }}>📦</span>
                   )}
                </div>
                <h3 className="product-title">{product.name}</h3>
                <div className="product-price">₹{Number(product.price).toFixed(2)}</div>
                <button className="btn-primary" style={{ width: '100%', marginTop: 'auto' }}>
                  Add to Cart
                </button>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
