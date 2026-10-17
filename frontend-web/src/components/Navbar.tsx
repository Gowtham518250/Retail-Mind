'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ShoppingBag, User, Package, LogIn, Sparkles, Trophy, Store, Home } from 'lucide-react';
import { useCart } from '../context/CartContext';
import styles from './Navbar.module.css';

export default function Navbar() {
  const pathname = usePathname();
  const { toggleCart, itemCount } = useCart();
  const shouldReduceMotion = Boolean(useReducedMotion());
  const [signedIn, setSignedIn] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [scrolled, setScrolled] = useState(false);
  const [hash, setHash] = useState('');

  useEffect(() => {
    const syncAuth = () => {
      const custToken = localStorage.getItem('customerToken');
      setSignedIn(Boolean(custToken));
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

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    const syncHash = () => setHash(window.location.hash);
    syncHash();
    window.addEventListener('hashchange', syncHash);
    window.addEventListener('popstate', syncHash);
    return () => {
      window.removeEventListener('hashchange', syncHash);
      window.removeEventListener('popstate', syncHash);
    };
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
    { href: '/#shops', label: 'Shops', icon: Store },
    { href: '/ai-shopping', label: 'AI Shop', icon: Sparkles },
    { href: signedIn ? '/orders' : '/auth?next=%2Forders', label: 'Orders', icon: Package },
    ...(signedIn ? [{ href: '/smart-shop', label: 'Smart Hub', icon: Trophy }] : []),
    { href: signedIn ? '/profile' : '/auth?next=%2Fprofile', label: 'Account', icon: User },
  ];

  return (
    <>
      <header className={styles.wrap}>
        <motion.nav
          className={`${styles.nav} ${scrolled ? styles.scrolled : ''}`}
          initial={shouldReduceMotion ? false : { y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 220, damping: 24 }}
          aria-label="Customer Primary Navigation"
        >
          <Link href="/" className={styles.brand} aria-label="Retail Mind home">
            <span className={styles.logo}><ShoppingBag size={18} strokeWidth={2.4} /></span>
            <span className={styles.word}>Retail<b>Mind</b></span>
          </Link>

          <div className={styles.actions}>
            {/* Desktop Navigation Links */}
            {desktopLinks.map(({ href, label, icon: Icon }) => {
              const active = pathname === href || (href !== '/' && pathname.startsWith(href + '/'));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`${styles.link} ${active ? styles.active : ''}`}
                  aria-label={label}
                  aria-current={active ? 'page' : undefined}
                >
                  {active && !shouldReduceMotion && (
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
                    initial={shouldReduceMotion ? false : { scale: 0.3, y: 8, opacity: 0 }}
                    animate={{ scale: 1, y: 0, opacity: 1 }}
                    exit={shouldReduceMotion ? undefined : { scale: 0.3, y: -8, opacity: 0 }}
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

      {/* ── Mobile Bottom Navigation Bar (Customer Only) ── */}
      <nav className={styles.mobileBottomNav} aria-label="Mobile Navigation">
        <div className={`${styles.bottomNavTrack} ${signedIn ? styles.bottomNavTrackSignedIn : ''}`}>
          {mobileNavItems.map(({ href, label, icon: Icon }) => {
            const active = label === 'Shops'
              ? pathname.startsWith('/shop') || (pathname === '/' && hash === '#shops')
              : href === '/'
                ? pathname === '/' && hash !== '#shops'
                : pathname === href || pathname.startsWith(href + '/');
            return (
              <Link
                key={label + href}
                href={href}
                className={`${styles.bottomNavItem} ${active ? styles.bottomNavItemActive : ''}`}
                aria-current={active ? 'page' : undefined}
                onClick={() => {
                  if (label === 'Shops') setHash('#shops');
                  else if (label === 'Home') setHash('');
                }}
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
