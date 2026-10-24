'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Package,
  LogOut,
  Mail,
  Phone,
  MapPin,
  ShieldCheck,
  CreditCard,
  Languages,
  CircleHelp,
  Settings,
  ChevronRight,
  ArrowLeft,
  ShoppingBag,
  Sparkles,
  CheckCircle2,
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
  const [profileNotice, setProfileNotice] = useState('');

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

  if (loading) {
    return (
      <main className={styles.profilePage} data-experience="profile">
        <div className={styles.container} role="status" aria-live="polite">
          <span className={styles.visuallyHidden}>Loading your account</span>
          <div className={`${styles.skeletonCard} ${styles.skeletonHeader}`}>
            <div className={styles.skeletonAvatar} />
            <div className={styles.skeletonTextGroup}>
              <div className={`${styles.skeletonLine} ${styles.skeletonName}`} />
              <div className={`${styles.skeletonLine} ${styles.skeletonContact}`} />
            </div>
          </div>
          <div className={`${styles.skeletonCard} ${styles.skeletonDetails}`}>
            <div className={`${styles.skeletonLine} ${styles.skeletonTitle}`} />
            <div className={styles.skeletonDetailsGrid}>
              <div className={styles.skeletonDetail} />
              <div className={styles.skeletonDetail} />
            </div>
          </div>
        </div>
      </main>
    );
  }

  const displayName = customer?.name || 'Shopper';
  const initial = displayName.trim().charAt(0).toUpperCase() || 'S';

  return (
    <main className={styles.profilePage} data-experience="profile">
      <div className={styles.container}>
        {/* Top Header */}
        <div className={styles.profilePageTop}>
          <Link href="/" className={styles.profileBack} aria-label="Back to shopping">
            <ArrowLeft size={19} />
          </Link>
          <h1>My Profile</h1>
        </div>

        {/* User Identity Card */}
        <section className={styles.profileHeaderCard} aria-label="Customer profile">
          <div className={styles.userInfoArea}>
            <div className={styles.avatarWrap}>
              <div className={styles.avatarInner}>
                <span>{initial}</span>
              </div>
              <span className={styles.avatarOnlineBadge} title="Active Member">
                <CheckCircle2 size={12} />
              </span>
            </div>

            <div className={styles.userMeta}>
              <div className={styles.userNameRow}>
                <h2 className={styles.userName}>{displayName}</h2>
                <span className={styles.verifiedChip}>
                  <Sparkles size={11} /> Verified Member
                </span>
              </div>
              <div className={styles.userContactRow}>
                {customer?.email && (
                  <span className={styles.contactItem}>
                    <Mail size={13} /> {customer.email}
                  </span>
                )}
                {customer?.phone && (
                  <span className={styles.contactItem}>
                    <Phone size={13} /> {customer.phone}
                  </span>
                )}
              </div>
            </div>
          </div>

          <Link href="/orders" className={styles.headerViewOrders} title="View my orders">
            <ShoppingBag size={17} />
          </Link>
        </section>

        {/* Quick Account Highlights */}
        <div className={styles.quickStatsRow}>
          <Link href="/orders" className={styles.quickStatCard}>
            <Package size={16} className={styles.statIconBlue} />
            <div>
              <strong>My Orders</strong>
              <small>Track &amp; reorder</small>
            </div>
          </Link>
          <a href="#addresses" className={styles.quickStatCard}>
            <MapPin size={16} className={styles.statIconGreen} />
            <div>
              <strong>Delivery Zone</strong>
              <small>{customer?.city || 'Local area'}</small>
            </div>
          </a>
        </div>

        {/* Profile Navigation Menu */}
        <section className={styles.profileMenuCard} aria-label="Profile and settings">
          <Link href="/orders" className={styles.profileMenuRow}>
            <span className={`${styles.profileMenuIcon} ${styles.iconOrders}`}>
              <Package size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>My Orders</strong>
              <small>View past orders &amp; receipts</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </Link>

          <a href="#addresses" className={styles.profileMenuRow}>
            <span className={`${styles.profileMenuIcon} ${styles.iconAddress}`}>
              <MapPin size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Delivery Addresses</strong>
              <small>Manage home &amp; work addresses</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </a>

          <button
            type="button"
            className={styles.profileMenuRow}
            onClick={() =>
              setProfileNotice(
                'Payment options (UPI, Cards, Cash on Delivery) are selected securely at checkout.'
              )
            }
          >
            <span className={`${styles.profileMenuIcon} ${styles.iconPayment}`}>
              <CreditCard size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Payment Methods</strong>
              <small>UPI, Cards, Net Banking</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </button>

          <button
            type="button"
            className={styles.profileMenuRow}
            onClick={() =>
              setProfileNotice(
                'This customer experience is currently set to English (default).'
              )
            }
          >
            <span className={`${styles.profileMenuIcon} ${styles.iconLang}`}>
              <Languages size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Language</strong>
              <small>English (Default)</small>
            </div>
            <span className={styles.profileMenuValue}>EN</span>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </button>

          <Link href="/contact" className={styles.profileMenuRow}>
            <span className={`${styles.profileMenuIcon} ${styles.iconHelp}`}>
              <CircleHelp size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Help &amp; Support</strong>
              <small>Customer assistance &amp; FAQs</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </Link>

          <a href="#settings" className={styles.profileMenuRow}>
            <span className={`${styles.profileMenuIcon} ${styles.iconSettings}`}>
              <Settings size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Account Settings</strong>
              <small>Security &amp; notifications</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </a>

          <button type="button" onClick={handleLogout} className={styles.profileMenuLogout}>
            <span className={`${styles.profileMenuIcon} ${styles.iconLogout}`}>
              <LogOut size={16} />
            </span>
            <div className={styles.profileMenuRowText}>
              <strong>Log Out</strong>
              <small>End current session</small>
            </div>
            <ChevronRight size={17} className={styles.profileMenuChevron} />
          </button>
        </section>

        {profileNotice && (
          <div className={styles.profileNotice} role="status" aria-live="polite">
            <p>{profileNotice}</p>
            <button type="button" onClick={() => setProfileNotice('')}>
              Dismiss
            </button>
          </div>
        )}

        {/* Saved Delivery Address Card */}
        <section id="addresses" className={styles.accountDetailsCard}>
          <div className={styles.cardHeaderWithAction}>
            <h2 className={styles.cardSectionTitle}>
              <MapPin size={16} /> Saved Delivery Address
            </h2>
            <span className={styles.defaultPill}>Default</span>
          </div>
          <div className={styles.detailsGrid}>
            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>Street Address</span>
              <span className={styles.detailValue}>
                {customer?.address || 'No address saved yet. Add your delivery address during checkout.'}
              </span>
            </div>
            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>City / Delivery Zone</span>
              <span className={styles.detailValue}>
                {customer?.city || 'Local neighbourhood zone'}
              </span>
            </div>
          </div>
        </section>

        {/* Account Security Card */}
        <section id="settings" className={styles.profileSecurityCard}>
          <span className={styles.profileSecurityIcon}>
            <ShieldCheck size={18} />
          </span>
          <div>
            <strong>Account Security &amp; Data Protection</strong>
            <p>Your Retail Mind account is protected with 256-bit SSL encryption and secure session tokens.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
