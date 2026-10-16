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
        <div className={styles.profileLayout}>
          <aside className={styles.profileSidebar}>
            <div className={styles.profileSidebarHeading}>
              <div className={styles.profileSidebarAvatar}>{displayName.charAt(0).toUpperCase()}</div>
              <div><strong>My Account</strong><span>Account settings</span></div>
            </div>
            <nav className={styles.profileMenu} aria-label="Account navigation">
              <Link href="/profile" className={styles.profileMenuActive}><ShoppingBag size={16} /> My Profile</Link>
              <Link href="#saved-addresses" className={styles.profileMenuLink}><MapPin size={16} /> Addresses</Link>
              <Link href="/orders" className={styles.profileMenuLink}><Package size={16} /> My Orders</Link>
              <Link href="/orders" className={styles.profileMenuLink}><Sparkles size={16} /> Reviews</Link>
              <Link href="/profile#notifications" className={styles.profileMenuLink}><ShieldCheck size={16} /> Notifications</Link>
              <Link href="/profile#account-security" className={styles.profileMenuLink}><ShieldCheck size={16} /> Settings</Link>
              <button type="button" className={styles.profileMenuLogout} onClick={() => setLogoutConfirmOpen(true)}><LogOut size={16} /> Logout</button>
            </nav>
            <div className={styles.profileSidebarFoot}>Your orders and account details stay linked to your customer account.</div>
          </aside>

          <div className={styles.profileContent}>
            <motion.header
              className={styles.profileDetailsHeader}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              <div>
                <span className={styles.profileOverline}>CUSTOMER PROFILE</span>
                <h1>{displayName}</h1>
                <p>Manage your profile, delivery information and account preferences.</p>
                <div className={styles.profileContactRow}>
                  {customer.email && <span><Mail size={14} /> {customer.email}</span>}
                  {customer.phone && <span><Phone size={14} /> {customer.phone}</span>}
                </div>
              </div>
              <span className={styles.profileVerified}><ShieldCheck size={14} /> Verified session</span>
            </motion.header>

            <motion.section
              className={styles.accountDetailsCard}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.05 }}
            >
              <div className={styles.profilePanelHeading}>
                <div><span>ACCOUNT</span><h2 className={styles.cardSectionTitle}>Personal information</h2></div>
              </div>
              <div className={styles.detailsGrid}>
                <div className={styles.detailBox}><span className={styles.detailLabel}>Full name</span><span className={styles.detailValue}>{displayName}</span></div>
                <div className={styles.detailBox}><span className={styles.detailLabel}>Email address</span><span className={styles.detailValue}>{customer.email || 'Not provided'}</span></div>
                <div className={styles.detailBox}><span className={styles.detailLabel}>Phone number</span><span className={styles.detailValue}>{customer.phone || 'Not provided'}</span></div>
              </div>
            </motion.section>

            <motion.section
              id="saved-addresses"
              className={styles.savedAddressPanel}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.1 }}
            >
              <div className={styles.profilePanelHeading}>
                <div><span>DELIVERY</span><h2>Saved Addresses</h2></div>
                <span className={styles.profileAddressDefault}>Default address</span>
              </div>
              <article className={styles.profileAddressCard}>
                <div className={styles.profileAddressIcon}><MapPin size={19} /></div>
                <div className={styles.profileAddressText}>
                  <strong>Home</strong>
                  <p>{customer.address || 'No saved address has been returned by your customer account.'}</p>
                  <span>{customer.city || 'City not provided'}</span>
                  {customer.phone && <span>{customer.phone}</span>}
                </div>
              </article>
              <p className={styles.profileAddressNote}>Address fields shown here are taken from your verified customer profile.</p>
            </motion.section>

            <motion.section
              id="account-security"
              className={styles.accountDetailsCard}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, delay: 0.14 }}
            >
              <div className={styles.profilePanelHeading}>
                <div><span>SECURITY</span><h2 className={styles.cardSectionTitle}>Account security</h2></div>
              </div>
              <div className={styles.profileSecurityRow}>
                <span className={styles.profileSecurityIcon}><ShieldCheck size={18} /></span>
                <div><strong>Customer session active</strong><p>Your profile was loaded from the authenticated customer API.</p></div>
                <Link href="/auth" className={styles.profileSecurityLink}>Sign in options <ArrowRight size={14} /></Link>
              </div>
            </motion.section>
          </div>
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
