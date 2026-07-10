'use client';

import { usePathname } from 'next/navigation';

export default function Navbar() {
  const pathname = usePathname();

  // Hide Navbar on the Auth page
  if (pathname === '/auth') {
    return null;
  }

  return (
    <nav className="navbar glass">
      <div className="container nav-content">
        <div className="nav-brand">Retail<span className="brand-accent">Shop</span></div>
        <div className="nav-search">
          <input type="text" className="input-field" placeholder="Search for products, brands and more" />
        </div>
        <div className="nav-actions">
          <button className="btn-secondary nav-login">Profile</button>
          <button className="btn-primary cart-btn">
            <span className="cart-icon">🛒</span> Cart
          </button>
        </div>
      </div>
    </nav>
  );
}
