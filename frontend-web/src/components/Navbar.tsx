'use client';

import { usePathname, useRouter } from 'next/navigation';
import { ShoppingBag, User, Package } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { useLanguage } from '../context/LanguageContext';

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleCart, itemCount } = useCart();
  const { language, setLanguage, languages, t } = useLanguage();

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
            className="nav-icon-btn"
            onClick={() => router.push('/orders')}
            aria-label="My orders"
            title={t('nav_orders')}
          >
            <Package size={20} />
            <span className="nav-icon-label">{t('nav_orders')}</span>
          </button>

          <button
            className="nav-icon-btn"
            onClick={() => router.push('/profile')}
            aria-label="Profile"
            title={t('nav_profile')}
          >
            <User size={20} />
            <span className="nav-icon-label">{t('nav_profile')}</span>
          </button>

          <label
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.04)',
              borderRadius: 10,
              padding: '4px 7px',
            }}
            title={t('nav_language')}
          >
            <span aria-hidden="true">🌐</span>
            <select
              value={language}
              onChange={(event) => setLanguage(event.target.value as typeof language)}
              style={{
                background: 'transparent',
                color: '#fff',
                border: 0,
                outline: 0,
                fontSize: 12,
                cursor: 'pointer',
              }}
              aria-label={t('nav_language')}
            >
              {languages.map((entry) => (
                <option key={entry.code} value={entry.code} style={{ color: '#111827' }}>
                  {entry.nativeName}
                </option>
              ))}
            </select>
          </label>

          <button
            className="cart-toggle-btn"
            onClick={toggleCart}
            aria-label={`Open cart, ${itemCount} items`}
            id="navbar-cart-btn"
          >
            <ShoppingBag size={19} />
            <span>{t('nav_cart')}</span>
            {itemCount > 0 && (
              <span className="cart-badge" aria-live="polite">{itemCount}</span>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}
