'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion } from 'framer-motion';
import { ShoppingBag, User, Package, LogIn, Sparkles, Trophy, Store, Home } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './Navbar.module.css';

export default function Navbar() {
  const pathname = usePathname();
  const { toggleCart, itemCount } = useCart();
  const [signedIn, setSignedIn] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [isSeller, setIsSeller] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const syncAuth = () => {
      const custToken = localStorage.getItem('customerToken');
      const merchToken = localStorage.getItem('merchantToken');
      const hasAuth = Boolean(custToken || merchToken);
      setSignedIn(hasAuth);
      setCustomerName(localStorage.getItem('customerName') || '');
      setIsSeller(localStorage.getItem('userRole') === 'OWNER' || Boolean(localStorage.getItem('shopId')));
    };
    syncAuth();
    window.addEventListener('storage', syncAuth);
    window.addEventListener('focus', syncAuth);
    return () => {
      window.removeEventListener('storage', syncAuth);
      window.removeEventListener('focus', syncAuth);
    };
  }, [pathname]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  if (pathname === '/auth') return null;

  const desktopLinks = [
    { href: '/ai-shopping', label: 'AI Shop', icon: Sparkles, show: true },
    { href: '/smart-shop', label: 'Smart Hub', icon: Trophy, show: signedIn },
    { href: '/orders', label: 'Orders', icon: Package, show: signedIn },
    { href: '/profile', label: customerName ? customerName.split(' ')[0] : 'Account', icon: User, show: signedIn },
    { href: '/auth', label: 'Sign in', icon: LogIn, show: !signedIn },
  ].filter((l) => l.show);

  const mobileNavItems = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/ai-shopping', label: 'AI Shop', icon: Sparkles },
    { href: isSeller ? '/profile' : '/sell', label: isSeller ? 'Store' : 'Sell', icon: Store },
    { href: signedIn ? '/orders' : '/auth', label: 'Orders', icon: Package },
    { href: signedIn ? '/profile' : '/auth', label: 'Account', icon: User },
  ];

  return (
    <>
      <header className={styles.wrap}>
        <motion.nav
          className={`${styles.nav} ${scrolled ? styles.scrolled : ''}`}
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 220, damping: 24 }}
          aria-label="Primary"
        >
          <Link href="/" className={styles.brand} aria-label="Retail Mind home">
            <span className={styles.logo}><ShoppingBag size={18} strokeWidth={2.4} /></span>
            <span className={styles.word}>Retail<b>Mind</b></span>
          </Link>

          <div className={styles.actions}>
            {/* Desktop Sell Button */}
            <Link
              href={isSeller ? '/profile' : '/sell'}
              className={styles.sellLink}
              aria-label="Sell on RetailMind"
            >
              <Store size={15} />
              <span>{isSeller ? 'My Store' : 'Sell Online'}</span>
            </Link>

            {/* Desktop Navigation Links */}
            {desktopLinks.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || pathname.startsWith(href + '/');
              return (
                <Link
                  key={href}
                  href={href}
                  className={`${styles.link} ${active ? styles.active : ''}`}
                  aria-label={label}
                  aria-current={active ? 'page' : undefined}
                >
                  {active && (
                    <motion.span
                      layoutId="navActive"
                      className={styles.activePill}
                      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
                    />
                  )}
                  <span className={styles.linkInner}>
                    <Icon size={17} />
                    <span className={styles.label}>{label}</span>
                  </span>
                </Link>
              );
            })}

            {/* Cart Trigger */}
            <button
              className={styles.cart}
              onClick={toggleCart}
              aria-label={'Open cart, ' + itemCount + ' items'}
              id="navbar-cart-btn"
            >
              <ShoppingBag size={18} />
              <span className={styles.cartLabel}>Cart</span>
              <AnimatePresence mode="popLayout" initial={false}>
                {itemCount > 0 && (
                  <motion.span
                    key={itemCount}
                    className={styles.badge}
                    aria-live="polite"
                    initial={{ scale: 0.3, y: 8, opacity: 0 }}
                    animate={{ scale: 1, y: 0, opacity: 1 }}
                    exit={{ scale: 0.3, y: -8, opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 520, damping: 18 }}
                  >
                    {itemCount}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          </div>
        </motion.nav>
      </header>

      {/* ── Mobile Bottom Navigation Bar ── */}
      <nav className={styles.mobileBottomNav} aria-label="Mobile Navigation">
        <div className={styles.bottomNavTrack}>
          {mobileNavItems.map(({ href, label, icon: Icon }) => {
            const active = href === '/' ? pathname === '/' : pathname.startsWith(href);
            return (
              <Link
                key={label + href}
                href={href}
                className={`${styles.bottomNavItem} ${active ? styles.bottomNavItemActive : ''}`}
              >
                <div className={styles.bottomNavIconWrap}>
                  <Icon size={20} strokeWidth={active ? 2.4 : 1.8} />
                  {active && <span className={styles.bottomActiveDot} />}
                </div>
                <span>{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
