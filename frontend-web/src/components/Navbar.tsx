'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { ShoppingBag, User, Package, LogIn, Sparkles, Trophy } from 'lucide-react';
import { useCart } from '../context/CartContext';

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleCart, itemCount } = useCart();
  const [signedIn, setSignedIn] = useState(false);
  const [customerName, setCustomerName] = useState('');

  useEffect(() => {
    const syncAuth = () => {
      setSignedIn(Boolean(localStorage.getItem('customerToken')));
      setCustomerName(localStorage.getItem('customerName') || '');
    };

    syncAuth();
    window.addEventListener('storage', syncAuth);
    window.addEventListener('focus', syncAuth);
    return () => {
      window.removeEventListener('storage', syncAuth);
      window.removeEventListener('focus', syncAuth);
    };
  }, [pathname]);

  if (pathname === '/auth') return null;

  return (
    <nav className="navbar">
      <div className="container nav-content">
        {/* Brand */}
        <div
          className="nav-brand"
          onClick={() => router.push('/')}
          role="button"
          aria-label="Go to home"
          tabIndex={0}
          onKeyDown={e => e.key === 'Enter' && router.push('/')}
        >
          <span className="nav-brand-icon"><ShoppingBag size={18} /></span>
          Retail<span className="brand-accent">Shop</span>
        </div>

        {/* Nav actions */}
        <div className="nav-actions">
          <button
            className="nav-icon-btn ai-nav-btn"
            onClick={() => router.push('/ai-shopping')}
            aria-label="AI Shopping"
            title="AI Shopping"
          >
            <Sparkles size={20} />
            <span className="nav-icon-label">AI Shop</span>
          </button>

          {signedIn ? (
            <>
              <button
                className="nav-icon-btn"
                onClick={() => router.push('/smart-shop')}
                aria-label="Smart shopping hub"
                title="Smart Shopping Hub"
              >
                <Trophy size={20} />
                <span className="nav-icon-label">Smart Hub</span>
              </button>

              <button
                className="nav-icon-btn"
                onClick={() => router.push('/orders')}
                aria-label="My orders"
                title="My Orders"
              >
                <Package size={20} />
                <span className="nav-icon-label">Orders</span>
              </button>

              <button
                className="nav-icon-btn"
                onClick={() => router.push('/profile')}
                aria-label="Profile"
                title="Profile"
              >
                <User size={20} />
                <span className="nav-icon-label">
                  {customerName ? customerName.split(' ')[0] : 'Account'}
                </span>
              </button>
            </>
          ) : (
            <button
              className="nav-icon-btn nav-signin-btn"
              onClick={() => router.push('/auth')}
              aria-label="Sign in"
              title="Sign in"
            >
              <LogIn size={19} />
              <span className="nav-icon-label">Sign in</span>
            </button>
          )}

          <button
            className="cart-toggle-btn"
            onClick={toggleCart}
            aria-label={`Open cart, ${itemCount} items`}
            id="navbar-cart-btn"
          >
            <ShoppingBag size={19} />
            <span>Cart</span>
            {itemCount > 0 && (
              <span className="cart-badge" aria-live="polite">{itemCount}</span>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}
