'use client';

import { useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Sparkles, Store, ShieldCheck, Zap } from 'lucide-react';
import { motion, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion';
import MarketScene from '../../components/MarketScene';
import styles from './splash.module.css';

const EASE = [0.16, 1, 0.3, 1] as const;

export default function SplashPage() {
  useEffect(() => {
    try {
      window.localStorage.setItem('retailMindIntroSeen', '1');
    } catch {
      /* optional preference */
    }
  }, []);

  const reduce = Boolean(useReducedMotion());

  // Pointer depth for the scene + chips (desktop mouse only; touch has no pointermove hover).
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const sx = useSpring(mx, { stiffness: 90, damping: 18 });
  const sy = useSpring(my, { stiffness: 90, damping: 18 });
  const sceneX = useTransform(sx, (v) => v * -10);
  const sceneY = useTransform(sy, (v) => v * -8);
  const chipX = useTransform(sx, (v) => v * 18);
  const chipY = useTransform(sy, (v) => v * 14);

  const onMove = (e: React.PointerEvent) => {
    if (reduce || e.pointerType !== 'mouse') return;
    const r = e.currentTarget.getBoundingClientRect();
    mx.set(((e.clientX - r.left) / r.width - 0.5) * 2);
    my.set(((e.clientY - r.top) / r.height - 0.5) * 2);
  };

  const rise = (delay: number) => ({
    initial: reduce ? false : { opacity: 0, y: 26 },
    animate: { opacity: 1, y: 0 },
    transition: { duration: 0.8, delay, ease: EASE },
  });

  return (
    <main className={styles.screen} data-entry-screen="splash" onPointerMove={onMove}>
      <div className={styles.aurora} aria-hidden="true">
        <i className={styles.blobA} />
        <i className={styles.blobB} />
        <i className={styles.blobC} />
        <i className={styles.grid} />
      </div>

      <header className={styles.topbar}>
        <div className={styles.topline}>
          <span className={styles.statusDot} />
          <span>HYPERLOCAL SHOPPING REIMAGINED</span>
        </div>
        <Link href="/auth" className={styles.quickSignIn}>Sign in</Link>
      </header>

      <section className={styles.stage}>
        <div className={styles.head}>
          <motion.div className={styles.logoWrap} {...rise(0)}>
            <Image src="/icons/retail-mind-logo.png" alt="Retail Mind" width={64} height={64} priority className={styles.logo} />
          </motion.div>
          <motion.span className={styles.brandPill} {...rise(0.08)}>
            <Sparkles size={13} /> Direct from nearby stores
          </motion.span>
          <motion.h1 className={styles.heroTitle} {...rise(0.16)}>
            Retail <span>Mind</span>
          </motion.h1>
          <motion.p className={styles.heroSubtitle} {...rise(0.26)}>
            Fresh groceries, daily essentials, and local favourites delivered straight from neighbourhood shelves.
          </motion.p>
        </div>

        <motion.div className={styles.sceneWrap} initial={reduce ? false : { opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.9, delay: 0.1, ease: EASE }}>
          <motion.div className={styles.scene} style={{ x: sceneX, y: sceneY }}>
            <MarketScene />
          </motion.div>

          <motion.div className={`${styles.chip} ${styles.chipTop}`} style={{ x: chipX, y: chipY }}>
            <span className={styles.badgeIcon}><Store size={14} /></span>
            <span>50+ Neighbourhood Shops</span>
          </motion.div>
          <motion.div className={`${styles.chip} ${styles.chipLeft}`} style={{ x: chipX, y: chipY }}>
            <span className={`${styles.badgeIcon} ${styles.badgeSpeed}`}><Zap size={14} /></span>
            <div><strong>15-20 Min</strong><small>Fast Doorstep Delivery</small></div>
          </motion.div>
          <motion.div className={`${styles.chip} ${styles.chipRight}`} style={{ x: chipX, y: chipY }}>
            <span className={`${styles.badgeIcon} ${styles.badgeTrust}`}><ShieldCheck size={14} /></span>
            <div><strong>100% Genuine</strong><small>Local Pricing &amp; Fresh Stock</small></div>
          </motion.div>
        </motion.div>

        <motion.div className={styles.cta} {...rise(0.4)}>
          <div className={styles.pageDots} aria-label="Welcome screen, 1 of 3">
            <span className={styles.dotActive} /><span /><span />
          </div>
          <Link href="/onboarding" className={styles.primaryButton}>
            <span>Explore Experience</span>
            <ArrowRight size={18} />
          </Link>
          <Link href="/" className={styles.secondaryLink}>Skip to Store Catalog</Link>
        </motion.div>
      </section>
    </main>
  );
}
