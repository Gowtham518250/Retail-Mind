'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import {
  ShoppingBag, ShoppingCart, User, Package, LogIn, Sparkles, Gift, Store, Home, Search, MapPin, ChevronDown,
} from 'lucide-react';
import { useCart } from '../context/CartContext';
import LocationModal from './LocationModal';
import styles from './Navbar.module.css';

const NO_CHROME = ['/auth', '/splash', '/onboarding'];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { toggleCart, itemCount } = useCart();
  const reduceMotion = Boolean(useReducedMotion());
  const [signedIn, setSignedIn] = useState(false);
  const [customerName, setCustomerName] = useState('');
  const [area, setArea] = useState('');
  const [query, setQuery] = useState('');
  const [locationModalOpen, setLocationModalOpen] = useState(false);

  useEffect(() => {
    const sync = () => {
      setSignedIn(Boolean(localStorage.getItem('customerToken')));
      setCustomerName(localStorage.getItem('customerName') || '');
      setArea(localStorage.getItem('retailMindArea') || '');
    };
    sync();
    window.addEventListener('storage', sync);
    window.addEventListener('focus', sync);
    window.addEventListener('retailmind:area', sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener('focus', sync);
      window.removeEventListener('retailmind:area', sync);
    };
  }, [pathname]);

  const hideChrome = NO_CHROME.includes(pathname);
  // Focused tasks keep the desktop shell but drop the mobile dock so it never covers a primary button.
  const focusedFlow = /\/checkout$|\/order-success$/.test(pathname) || /^\/orders\/[^/]+/.test(pathname);

  useEffect(() => {
    if (hideChrome) return;
    document.body.setAttribute('data-shell', 'true');
    if (!focusedFlow) document.body.setAttribute('data-dock', 'true');
    return () => {
      document.body.removeAttribute('data-shell');
      document.body.removeAttribute('data-dock');
    };
  }, [hideChrome, focusedFlow]);

  if (hideChrome) return null;

  const isActive = (href: string) => {
    const base = href.split('?')[0];
    if (base === '/') return pathname === '/';
    if (base === '/shops') return pathname === '/shops' || pathname.startsWith('/shop/');
    return pathname === base || pathname.startsWith(base + '/');
  };

  const navItems = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/shops', label: 'Shops', icon: Store },
    { href: '/ai-shopping', label: 'AI shopping', icon: Sparkles },
    { href: signedIn ? '/smart-shop' : '/auth?next=%2Fsmart-shop', label: 'Rewards', icon: Gift },
    { href: signedIn ? '/orders' : '/auth?next=%2Forders', label: 'Orders', icon: Package },
    { href: signedIn ? '/profile' : '/auth?next=%2Fprofile', label: signedIn ? (customerName.split(' ')[0] || 'Profile') : 'Profile', icon: User },
  ];
  const dockItems = [
    { href: '/', label: 'Home', icon: Home },
    { href: '/shops', label: 'Shops', icon: Store },
    { href: '#cart', label: 'Cart', icon: ShoppingCart },
    { href: signedIn ? '/orders' : '/auth?next=%2Forders', label: 'Orders', icon: Package },
    { href: signedIn ? '/profile' : '/auth?next=%2Fprofile', label: 'Profile', icon: User },
  ];

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    router.push(q ? '/?q=' + encodeURIComponent(q) : '/');
  };

  return (
    <>
      {/* Desktop: top bar + left sidebar. Mobile: CSS hides both and the dock below takes over. */}
      <header className={styles.topbar}>
        <div className={styles.topbarInner}>
          <div className={styles.leftGroup}>
            <Link href="/" className={styles.brand} aria-label="Retail Mind home">
              <motion.span
                className={styles.logo}
                whileHover={reduceMotion ? undefined : { rotate: -10, scale: 1.08 }}
                transition={{ type: 'spring', stiffness: 400, damping: 16 }}
              >
                <ShoppingBag size={20} strokeWidth={2.4} />
              </motion.span>
              <span className={styles.word}>Retail<b>Mind</b></span>
            </Link>

            <button
              type="button"
              className={styles.area}
              onClick={() => setLocationModalOpen(true)}
              title="Change delivery location"
              aria-label={'Deliver to ' + (area || 'your neighbourhood') + ', click to change location'}
            >
              <MapPin size={16} className={styles.areaPin} />
              <span>
                <small>Deliver to</small>
                <strong>{area || 'Select Location'}</strong>
              </span>
              <ChevronDown size={14} className={styles.areaChevron} />
            </button>
          </div>

          <form className={styles.search} role="search" onSubmit={submitSearch}>
            <Search size={18} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search products or shops"
              aria-label="Search products or shops"
            />
            <button type="submit" aria-label="Search">Search</button>
          </form>

          <div className={styles.topActions}>
            {!signedIn && (
              <Link href="/auth" className={styles.signIn}><LogIn size={17} /> Sign in</Link>
            )}
            <button className={styles.cart} onClick={toggleCart} id="navbar-cart-btn" aria-label={'Open cart, ' + itemCount + ' items'}>
              <ShoppingCart size={19} />
              <span className={styles.cartLabel}>Cart</span>
              <AnimatePresence mode="popLayout" initial={false}>
                {itemCount > 0 && (
                  <motion.span
                    key={itemCount}
                    className={styles.badge}
                    aria-live="polite"
                    initial={reduceMotion ? false : { scale: 0.3, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    exit={reduceMotion ? undefined : { scale: 0.3, opacity: 0 }}
                    transition={{ type: 'spring', stiffness: 520, damping: 18 }}
                  >
                    {itemCount}
                  </motion.span>
                )}
              </AnimatePresence>
            </button>
          </div>
        </div>
      </header>

      <nav className={styles.sidebar} aria-label="Customer navigation">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href);
          return (
            <Link key={label} href={href} className={`${styles.sideLink} ${active ? styles.sideActive : ''}`} aria-current={active ? 'page' : undefined}>
              {active && !reduceMotion && (
                <motion.span layoutId="sideActive" className={styles.sidePill} transition={{ type: 'spring', stiffness: 400, damping: 34 }} />
              )}
              <span className={styles.sideInner}><Icon size={19} /> {label}</span>
            </Link>
          );
        })}
        <div className={styles.sideHelp}>
          <strong>Need a hand?</strong>
          <span>Ask the AI shopping assistant to build your basket.</span>
          <Link href="/ai-shopping">Try AI shopping</Link>
        </div>
      </nav>

      {!focusedFlow && (
        <nav className={styles.dock} aria-label="Mobile navigation">
          <div className={styles.dockTrack}>
            {dockItems.map(({ href, label, icon: Icon }) => {
              if (label === 'Cart') {
                return (
                  <button key={label} type="button" className={styles.dockItem} onClick={toggleCart} aria-label={'Open cart, ' + itemCount + ' items'}>
                    <span className={styles.dockIcon}>
                      <Icon size={22} strokeWidth={1.9} />
                      {itemCount > 0 && <span className={styles.dockDot}>{itemCount > 9 ? '9+' : itemCount}</span>}
                    </span>
                    <span>{label}</span>
                  </button>
                );
              }
              const active = isActive(href);
              return (
                <Link key={label} href={href} className={`${styles.dockItem} ${active ? styles.dockActive : ''}`} aria-current={active ? 'page' : undefined}>
                  <span className={styles.dockIcon}>
                    {active && !reduceMotion && (
                      <motion.span layoutId="dockActive" className={styles.dockPill} transition={{ type: 'spring', stiffness: 420, damping: 32 }} />
                    )}
                    <Icon size={22} strokeWidth={active ? 2.4 : 1.9} />
                  </span>
                  <span>{label}</span>
                </Link>
              );
            })}
          </div>
        </nav>
      )}

      <LocationModal
        isOpen={locationModalOpen}
        onClose={() => setLocationModalOpen(false)}
        onLocationSelected={(newArea: string) => {
          setArea(newArea);
        }}
      />
    </>
  );
}
