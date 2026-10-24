'use client';

import { useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Sparkles, Store, ShieldCheck, Zap } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import styles from './splash.module.css';

export default function SplashPage() {
  useEffect(() => {
    try {
      window.localStorage.setItem('retailMindIntroSeen', '1');
    } catch {
      /* optional preference */
    }
  }, []);

  const reduceMotion = Boolean(useReducedMotion());

  return (
    <main className={styles.screen} data-entry-screen="splash">
      {/* Background soft ambient orbs */}
      <div className={styles.ambientGlowTop} aria-hidden="true" />
      <div className={styles.ambientGlowBottom} aria-hidden="true" />

      <header className={styles.topbar}>
        <div className={styles.topline}>
          <span className={styles.statusDot} />
          <span>HYPERLOCAL SHOPPING REIMAGINED</span>
        </div>
        <Link href="/auth" className={styles.quickSignIn}>Sign in</Link>
      </header>

      <section className={styles.content}>
        <motion.div
          className={styles.brandBlock}
          initial={reduceMotion ? false : { opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.4 }}
        >
          <div className={styles.logoWrap}>
            <Image
              src="/icons/retail-mind-logo.png"
              alt="Retail Mind"
              width={76}
              height={76}
              priority
              className={styles.logo}
            />
          </div>
          <span className={styles.brandPill}>
            <Sparkles size={13} /> Direct from nearby stores
          </span>
          <h1 className={styles.heroTitle}>
            Retail <span>Mind</span>
          </h1>
          <p className={styles.heroSubtitle}>
            Fresh groceries, daily essentials, and local favourites delivered straight from neighbourhood shelves.
          </p>
        </motion.div>

        {/* Hero showcase card with authentic photography */}
        <motion.div
          className={styles.heroVisualCard}
          initial={reduceMotion ? false : { opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.45, delay: 0.08 }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80"
            alt="Fresh grocery and neighbourhood produce market"
            className={styles.heroImage}
            loading="eager"
          />
          <div className={styles.heroOverlay} />

          {/* Floating glass badges */}
          <div className={styles.heroBadgeTop}>
            <span className={styles.badgeIcon}><Store size={14} /></span>
            <span>50+ Neighbourhood Shops</span>
          </div>

          <div className={styles.heroBadgeBottomLeft}>
            <span className={`${styles.badgeIcon} ${styles.badgeSpeed}`}><Zap size={14} /></span>
            <div>
              <strong>15-20 Min</strong>
              <small>Fast Doorstep Delivery</small>
            </div>
          </div>

          <div className={styles.heroBadgeBottomRight}>
            <span className={`${styles.badgeIcon} ${styles.badgeTrust}`}><ShieldCheck size={14} /></span>
            <div>
              <strong>100% Genuine</strong>
              <small>Local Pricing & Fresh Stock</small>
            </div>
          </div>
        </motion.div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.pageDots} aria-label="Welcome screen, 1 of 3">
          <span className={styles.dotActive} />
          <span />
          <span />
        </div>

        <Link href="/onboarding" className={styles.primaryButton}>
          <span>Explore Experience</span>
          <ArrowRight size={18} />
        </Link>

        <Link href="/" className={styles.secondaryLink}>
          Skip to Store Catalog
        </Link>
      </footer>
    </main>
  );
}
