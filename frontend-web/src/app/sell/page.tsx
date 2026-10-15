'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Store,
  Sparkles,
  ArrowRight,
  TrendingUp,
  QrCode,
  CheckCircle,
  ShieldCheck,
  Zap,
  Boxes,
  Users,
} from 'lucide-react';
import styles from './sell.module.css';

export default function SellPage() {
  const [signedInRole, setSignedInRole] = useState<string | null>(null);
  const [shopId, setShopId] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setSignedInRole(localStorage.getItem('userRole'));
    setShopId(localStorage.getItem('shopId'));
  }, []);

  const isSeller = signedInRole === 'OWNER' || Boolean(shopId);

  return (
    <main className={styles.sellMain}>
      <div className={styles.orb1} />
      <div className={styles.orb2} />

      <div className={styles.container}>
        {/* ── 1. Hero Section ── */}
        <section className={styles.heroSection}>
          <motion.div
            className={styles.heroContent}
            initial={{ opacity: 0, x: -30 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.65 }}
          >
            <div className={styles.badgePill}>
              <Sparkles size={14} />
              <span>Merchant & Seller Program</span>
            </div>

            <h1 className={styles.heroTitle}>
              Grow Your Business.{' '}
              <span className={styles.heroGradient}>Zero Platform Commission.</span>
            </h1>

            <p className={styles.heroLead}>
              Open your digital store in 60 seconds. Sell groceries, electronics, apparel, or daily essentials
              directly to neighborhood shoppers with instant UPI QR payments.
            </p>

            <div className={styles.heroActions}>
              {isSeller ? (
                <Link href="/profile" className={styles.primaryCta}>
                  <Store size={18} />
                  <span>Go to Store Manager</span>
                  <ArrowRight size={16} />
                </Link>
              ) : (
                <Link href="/auth?role=seller" className={styles.primaryCta}>
                  <Store size={18} />
                  <span>Open Your Store Now</span>
                  <ArrowRight size={16} />
                </Link>
              )}
              <Link href="/" className={styles.secondaryCta}>
                <span>Explore Marketplace</span>
              </Link>
            </div>
          </motion.div>

          {/* 3D Visual Metric Card */}
          <motion.div
            className={styles.heroVisualCard}
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.15 }}
          >
            <div className={styles.visualCardTop}>
              <span className={styles.statusIndicator}>
                <span className={styles.pulseDot} />
                Live Settlements Active
              </span>
              <QrCode size={24} color="#f59e0b" />
            </div>

            <div className={styles.comparisonBox}>
              <div className={`${styles.compareCol} ${styles.compareOurs}`}>
                <span className={styles.compareLabel}>RetailMind Fee</span>
                <span className={`${styles.compareFee} ${styles.feeZero}`}>0%</span>
                <span className={styles.compareNote}>Keep 100% of your earnings. Direct to your UPI.</span>
              </div>

              <div className={`${styles.compareCol} ${styles.compareTheirs}`}>
                <span className={styles.compareLabel}>Aggregators</span>
                <span className={`${styles.compareFee} ${styles.feeHeavy}`}>18-28%</span>
                <span className={styles.compareNote}>Heavy commissions + delayed weekly payouts.</span>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#cbd5e1' }}>
                <CheckCircle size={16} color="#10b981" />
                <span>Instant voice & audio confirmation on every payment</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', color: '#cbd5e1' }}>
                <CheckCircle size={16} color="#10b981" />
                <span>Publish unlimited products with photos & inventory counts</span>
              </div>
            </div>
          </motion.div>
        </section>

        {/* ── 2. How it works (3-Step Process) ── */}
        <section className={styles.stepsSection}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>How to Start Selling Online</h2>
            <p className={styles.sectionSubtitle}>
              Three simple steps to transform your physical retail shop into a powerful digital storefront.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <motion.div
              className={styles.stepCard}
              whileHover={{ y: -5 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepCardTitle}>Register in 60 Seconds</h3>
              <p className={styles.stepCardText}>
                Provide your store name, owner details, and select your category. Your online storefront URL and QR code are generated immediately.
              </p>
            </motion.div>

            <motion.div
              className={styles.stepCard}
              whileHover={{ y: -5 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepCardTitle}>List Your Products</h3>
              <p className={styles.stepCardText}>
                Add items with unit prices, stock levels, and pictures using our web catalog creator or AI-powered scanner.
              </p>
            </motion.div>

            <motion.div
              className={styles.stepCard}
              whileHover={{ y: -5 }}
              transition={{ duration: 0.2 }}
            >
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepCardTitle}>Direct Customer Orders</h3>
              <p className={styles.stepCardText}>
                Shoppers order directly from your link. Money goes straight to your UPI account without middlemen or holding periods.
              </p>
            </motion.div>
          </div>
        </section>

        {/* ── 3. Bottom Launch Banner ── */}
        <section className={styles.ctaBanner}>
          <div className={styles.ctaBannerLeft}>
            <h3>Ready to expand your local footprint?</h3>
            <p>
              Join hundreds of neighborhood stores and creators already selling on RetailMind. No hidden setup costs.
            </p>
          </div>

          {isSeller ? (
            <Link href="/profile" className={styles.primaryCta}>
              <Store size={18} />
              <span>Open Store Dashboard</span>
              <ArrowRight size={16} />
            </Link>
          ) : (
            <Link href="/auth?role=seller" className={styles.primaryCta}>
              <Store size={18} />
              <span>Launch Store Free</span>
              <ArrowRight size={16} />
            </Link>
          )}
        </section>
      </div>
    </main>
  );
}
