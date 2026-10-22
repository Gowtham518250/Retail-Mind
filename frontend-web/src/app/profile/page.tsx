'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
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
        <div className={styles.orbA} />
        <div className={styles.orbB} />
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
              <div className={styles.skeletonDetail} />
            </div>
          </div>
          <div className={styles.skeletonCards}>
            <div className={styles.skeletonCard} />
            <div className={styles.skeletonCard} />
            <div className={styles.skeletonCard} />
          </div>
        </div>
      </main>
    );
  }

  const displayName = customer?.name || 'Shopper';

  return (
    <main className={styles.profilePage} data-experience="profile">
      <div className={styles.container}>
        <div className={styles.profilePageTop}>
          <Link href="/" className={styles.profileBack} aria-label="Back to shopping">
            <ArrowLeft size={19} />
          </Link>
          <h1>My Profile</h1>
        </div>

        <section className={styles.profileHeaderCard} aria-label="Customer profile">
          <div className={styles.userInfoArea}>
            <div className={styles.avatarAura}>
              <div className={styles.avatarInner}><Image src="/icons/customer-avatar.svg" alt="" width={44} height={44} className={styles.profileAvatarImage} priority /></div>
            </div>
            <div className={styles.userMeta}>
              <h2 className={styles.userName}>{displayName}</h2>
              <div className={styles.userContactRow}>
                {customer?.email && <span><Mail size={12} />{customer.email}</span>}
                {customer?.phone && <span><Phone size={12} />{customer.phone}</span>}
              </div>
            </div>
          </div>
          <span className={styles.profileHeaderChevron}><ChevronRight size={19} /></span>
        </section>

        <section className={styles.profileMenuCard} aria-label="Profile and settings">
          <Link href="/orders" className={styles.profileMenuRow}>
            <span className={styles.profileMenuIcon}><Package size={16} /></span>
            <span className={styles.profileMenuRowText}>My Orders</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </Link>
          <a href="#addresses" className={styles.profileMenuRow}>
            <span className={styles.profileMenuIcon}><MapPin size={16} /></span>
            <span className={styles.profileMenuRowText}>Addresses</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </a>
          <button
            type="button"
            className={styles.profileMenuRow}
            onClick={() => setProfileNotice('Payment options are selected securely at checkout. Saved payment methods are not stored in this web profile yet.')}
          >
            <span className={styles.profileMenuIcon}><CreditCard size={16} /></span>
            <span className={styles.profileMenuRowText}>Payment Methods</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </button>
          <button
            type="button"
            className={styles.profileMenuRow}
            onClick={() => setProfileNotice('This customer web experience is currently set to English. Language switching is not available here yet.')}
          >
            <span className={styles.profileMenuIcon}><Languages size={16} /></span>
            <span className={styles.profileMenuRowText}>Language</span>
            <span className={styles.profileMenuValue}>English</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </button>
          <Link href="/contact" className={styles.profileMenuRow}>
            <span className={styles.profileMenuIcon}><CircleHelp size={16} /></span>
            <span className={styles.profileMenuRowText}>Help &amp; Support</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </Link>
          <a href="#settings" className={styles.profileMenuRow}>
            <span className={styles.profileMenuIcon}><Settings size={16} /></span>
            <span className={styles.profileMenuRowText}>Settings</span>
            <ChevronRight size={16} className={styles.profileMenuChevron} />
          </a>
          <button type="button" onClick={handleLogout} className={styles.profileMenuLogout}>
            <LogOut size={16} />
            <span>Logout</span>
            <ChevronRight size={16} />
          </button>
        </section>

        {profileNotice && (
          <div className={styles.profileNotice} role="status" aria-live="polite">
            <p>{profileNotice}</p>
            <button type="button" onClick={() => setProfileNotice('')}>Dismiss</button>
          </div>
        )}

        <section id="addresses" className={styles.accountDetailsCard}>
          <h2 className={styles.cardSectionTitle}><MapPin size={16} /> Saved Delivery Address</h2>
          <div className={styles.detailsGrid}>
            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>Address</span>
              <span className={styles.detailValue}>{customer?.address || 'No address saved yet. Add your delivery address during checkout.'}</span>
            </div>
            <div className={styles.detailBox}>
              <span className={styles.detailLabel}>City / Area</span>
              <span className={styles.detailValue}>{customer?.city || 'Local delivery zone'}</span>
            </div>
          </div>
        </section>

        <section id="settings" className={styles.profileSecurityCard}>
          <span className={styles.profileSecurityIcon}><ShieldCheck size={17} /></span>
          <div>
            <strong>Account security</strong>
            <p>Your Retail Mind customer account is protected by your sign-in credentials.</p>
          </div>
        </section>
      </div>
    </main>
  );
}
