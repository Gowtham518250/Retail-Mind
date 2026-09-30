'use client';

import { usePathname, useRouter } from 'next/navigation';
import { ShoppingBag, User, Package } from 'lucide-react';
import { useCart } from '../context/CartContext';
import { WEB_LANGUAGES, useWebLanguage } from '../context/LanguageContext';

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleCart, itemCount } = useCart();
  const { language, setLanguage, t } = useWebLanguage();

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
          <label className="nav-language-control" aria-label={t('language')}>
            <span>🌐</span>
            <select
              value={language}
              onChange={e => setLanguage(e.target.value as any)}
            >
              {WEB_LANGUAGES.map(item => (
                <option key={item.code} value={item.code}>
                  {item.native}
                </option>
              ))}
            </select>
          </label>
          <button
            className="nav-icon-btn"
            onClick={() => router.push('/orders')}
            aria-label="My orders"
            title={t('orders')}
          >
            <Package size={20} />
            <span className="nav-icon-label">{t('orders')}</span>
          </button>

          <button
            className="nav-icon-btn"
            onClick={() => router.push('/profile')}
            aria-label="Profile"
            title={t('profile')}
          >
            <User size={20} />
            <span className="nav-icon-label">{t('profile')}</span>
          </button>

          <button
            className="cart-toggle-btn"
            onClick={toggleCart}
            aria-label={`Open cart, ${itemCount} items`}
            id="navbar-cart-btn"
          >
            <ShoppingBag size={19} />
            <span>{t('cart')}</span>
            {itemCount > 0 && (
              <span className="cart-badge" aria-live="polite">{itemCount}</span>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}
