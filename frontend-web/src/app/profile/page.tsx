'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
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

        const data = await res.json();
        if (data && data.customer) {
          setCustomer(data.customer);
          localStorage.setItem('customerName', data.customer.name || 'Shopper');
          if (data.customer.email) localStorage.setItem('customerEmail', data.customer.email);
        } else {
          // Fallback to localStorage data
          setCustomer({
            id: 0,
            name: localStorage.getItem('customerName') || 'Shopper',
            email: localStorage.getItem('customerEmail') || '',
          });
        }
      } catch {
        setCustomer({
          id: 0,
          name: localStorage.getItem('customerName') || 'Shopper',
          email: localStorage.getItem('customerEmail') || '',
        });
      } finally {
        setLoading(false);
      }
    };

    loadCustomer();
  }, [router]);

  const handleLogout = () => {
    localStorage.removeItem('customerToken');
    localStorage.removeItem('customerName');
    localStorage.removeItem('customerEmail');
    localStorage.removeItem('userRole');
    router.push('/');
  };

  if (loading) return null;

  const displayName = customer?.name || 'Shopper';

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
                  Verified Shopper
                </span>
              </div>

              <div className={styles.userContactRow}>
                {customer?.email && (
                  <span>
                    <Mail size={13} />
                    {customer.email}
                  </span>
                )}
                {customer?.phone && (
                  <span>
                    <Phone size={13} />
                    {customer.phone}
                  </span>
                )}
              </div>
            </div>
          </div>

          <button type="button" onClick={handleLogout} className={styles.logoutBtn}>
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
                {customer?.address || 'No address saved yet (added during checkout)'}
              </span>
            </div>

            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>City / Area</span>
              <span className={styles.detailValue}>
                {customer?.city || 'Local Delivery Zone'}
              </span>
            </div>

            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>Account Security</span>
              <span className={styles.detailValue} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#34d399' }}>
                <ShieldCheck size={16} /> Verified &amp; Protected
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
                Explore Verified Shops <ArrowRight size={16} />
              </h3>
              <p className={styles.navCardDesc}>
                Discover local grocery, bakery, electronics, and daily essential storefronts near you.
              </p>
            </div>
          </Link>
        </div>
      </div>
    </main>
  );
}
