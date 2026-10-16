'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { AnimatePresence, motion } from 'framer-motion';
import {
  ShoppingBag,
  Package,
  Sparkles,
  Trophy,
  LogOut,
  Mail,
  Phone,
  MapPin,
  ShieldCheck,
  ArrowRight,
  Store,
  X,
} from 'lucide-react';
import { API_BASE } from '../../lib/api';
import styles from './profile.module.css';

interface CustomerData {
  id: number;
  name: string;
  email?: string | null;
  phone?: string | null;
  address?: string | null;
  city?: string | null;
}

export default function ProfilePage() {
  const router = useRouter();
  const [customer, setCustomer] = useState<CustomerData | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const token = localStorage.getItem('customerToken');
    if (!token) {
      router.push('/auth');
      return;
    }

    const loadCustomer = async () => {
      try {
        const res = await fetch(`${API_BASE}/store/customer/me`, {
          headers: { Authorization: `Bearer ${token}` },
          cache: 'no-store',
        });

        if (res.status === 401 || res.status === 403) {
          localStorage.removeItem('customerToken');
          localStorage.removeItem('customerName');
          localStorage.removeItem('customerEmail');
          router.push('/auth');
          return;
        }

        if (!res.ok) throw new Error('Your customer profile could not be verified.');
        const data = await res.json();
        if (!data?.customer) throw new Error('The customer profile response was incomplete.');
        setCustomer(data.customer as CustomerData);
        localStorage.setItem('customerName', data.customer.name || 'Shopper');
        if (data.customer.email) localStorage.setItem('customerEmail', data.customer.email);
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : 'Unable to load your customer profile. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    loadCustomer();
  }, [router]);

  useEffect(() => {
    if (!logoutConfirmOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setLogoutConfirmOpen(false);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [logoutConfirmOpen]);

  const handleLogout = () => {
    localStorage.removeItem('customerToken');
    localStorage.removeItem('customerName');
    localStorage.removeItem('customerEmail');
    localStorage.removeItem('userRole');
    router.push('/');
  };

  if (loading) {
    return (
      <main className={styles.profilePage} aria-busy="true">
        <div className={styles.container}>
          <section className={styles.accountDetailsCard} role="status">Loading your customer account…</section>
        </div>
      </main>
    );
  }

  if (loadError || !customer) {
    return (
      <main className={styles.profilePage}>
        <div className={styles.container}>
          <section className={styles.accountDetailsCard} role="alert">
            <h1>Account temporarily unavailable</h1>
            <p>{loadError || 'We could not verify your customer account.'}</p>
            <p>Your account details are hidden until the server confirms your identity.</p>
            <button type="button" onClick={() => window.location.reload()} className={styles.logoutBtn}>Retry</button>
          </section>
        </div>
      </main>
    );
  }

  const displayName = customer.name || 'Shopper';

  return (
    <main className={styles.profilePage}>
      {/* 3D Ambient Orbs */}
      <div className={styles.orbA} />
      <div className={styles.orbB} />

      <div className={styles.container}>
        {/* ── 1. Header Card ── */}
        <motion.div
          className={styles.profileHeaderCard}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55 }}
        >
          <div className={styles.headerGlowLine} />

          <div className={styles.userInfoArea}>
            <div className={styles.avatarAura}>
              <div className={styles.avatarInner}>
                {displayName.charAt(0).toUpperCase()}
              </div>
            </div>

            <div className={styles.userMeta}>
              <div className={styles.userNameRow}>
                <h1 className={styles.userName}>{displayName}</h1>
                <span className={styles.roleBadge}>
                  <ShoppingBag size={13} />
                  Customer Account
                </span>
              </div>

              <div className={styles.userContactRow}>
                {customer.email && (
                  <span>
                    <Mail size={13} />
                    {customer.email}
                  </span>
                )}
                {customer.phone && (
                  <span>
                    <Phone size={13} />
                    {customer.phone}
                  </span>
                )}
              </div>
            </div>
          </div>

          <button type="button" onClick={() => setLogoutConfirmOpen(true)} className={styles.logoutBtn}>
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </motion.div>

        {/* ── 2. Account & Delivery Details ── */}
        <motion.div
          className={styles.accountDetailsCard}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, delay: 0.1 }}
        >
          <h2 className={styles.cardSectionTitle}>
            <MapPin size={18} color="#38bdf8" />
            Saved Delivery Information
          </h2>

          <div className={styles.detailsGrid}>
            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>Default Address</span>
              <span className={styles.detailValue}>
                {customer.address || 'No saved address returned by the account API.'}
              </span>
            </div>

            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>City / Area</span>
              <span className={styles.detailValue}>
                {customer.city || 'Not provided'}
              </span>
            </div>

            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>Account Security</span>
              <span className={styles.detailValue} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#34d399' }}>
                <ShieldCheck size={16} /> Authenticated customer profile
              </span>
            </div>
          </div>
        </motion.div>

        {/* ── 3. Customer Hub Bento Navigation ── */}
        <div className={styles.bentoNavGrid}>
          <Link href="/orders" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Package size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                My Orders &amp; Tracking <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>
                Track live package dispatch, view real-time delivery status, submit product ratings, or cancel eligible orders.
              </p>
            </div>
          </Link>

          <Link href="/smart-shop" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Trophy size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                Smart Shopping Hub <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>
                AI-driven smart baskets, cross-store price comparisons, and personalized recommendations.
              </p>
            </div>
          </Link>

          <Link href="/" className={styles.navCard}>
            <div className={styles.navCardIcon}>
              <Store size={22} />
            </div>
            <div>
              <h3 className={styles.navCardTitle}>
                Explore Local Shops <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>
                Discover local grocery, bakery, electronics, and daily essential storefronts near you.
              </p>
            </div>
          </Link>
        </div>
      </div>

      <AnimatePresence>
        {logoutConfirmOpen && (
          <motion.div
            className={styles.logoutOverlay}
            role="presentation"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setLogoutConfirmOpen(false);
            }}
          >
            <motion.section
              className={styles.logoutDialog}
              role="dialog"
              aria-modal="true"
              aria-labelledby="logout-dialog-title"
              aria-describedby="logout-dialog-description"
              initial={{ opacity: 0, y: 16, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.18 }}
            >
              <button
                type="button"
                className={styles.logoutDialogClose}
                onClick={() => setLogoutConfirmOpen(false)}
                aria-label="Close sign-out confirmation"
              >
                <X size={18} />
              </button>
              <div className={styles.logoutDialogIcon}><LogOut size={25} /></div>
              <span className={styles.logoutDialogEyebrow}>ACCOUNT SESSION</span>
              <h2 id="logout-dialog-title">Sign out of Retail Mind?</h2>
              <p id="logout-dialog-description">
                You’ll be signed out on this device. Your orders remain saved to your customer account, and you can sign in again anytime.
              </p>
              <div className={styles.logoutDialogActions}>
                <button
                  type="button"
                  className={styles.logoutCancelBtn}
                  onClick={() => setLogoutConfirmOpen(false)}
                >
                  Stay signed in
                </button>
                <button
                  type="button"
                  className={styles.logoutConfirmBtn}
                  onClick={handleLogout}
                >
                  <LogOut size={16} /> Sign out
                </button>
              </div>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
