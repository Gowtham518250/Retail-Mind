'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useCart } from '../context/CartContext';

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleCart, itemCount } = useCart();

  // Hide Navbar on the Auth page
  if (pathname === '/auth') {
    return null;
  }

  return (
    <nav className="navbar glass">
      <div className="container nav-content">
        <div className="nav-brand" onClick={() => router.push('/')} style={{cursor: 'pointer'}}>Retail<span className="brand-accent">Shop</span></div>
        <div className="nav-search">
          <input type="text" className="input-field" placeholder="Search for products, brands and more" />
        </div>
        <div className="nav-actions">
          <button className="btn-secondary nav-login" onClick={() => router.push('/profile')}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{marginRight: '6px'}}><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            Profile
          </button>
          <button className="btn-primary cart-btn" onClick={toggleCart}>
            <span className="cart-icon">🛒</span> Cart {itemCount > 0 && `(${itemCount})`}
          </button>
        </div>
      </div>
    </nav>
  );
}
