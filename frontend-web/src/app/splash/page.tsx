'use client';

import { useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Leaf, ShoppingBag, ShoppingBasket, Sparkles } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import styles from './splash.module.css';

export default function SplashPage() {
  useEffect(() => {
    try { window.localStorage.setItem('retailMindIntroSeen', '1'); } catch { /* optional preference */ }
  }, []);

  const reduceMotion = Boolean(useReducedMotion());

  return (
    <main className={styles.screen} data-entry-screen="splash">
      <div className={styles.topline}>
        <span className={styles.statusDot} />
        <span>LOCAL SHOPPING, MADE SIMPLE</span>
      </div>

      <section className={styles.content}>
        <motion.div
          className={styles.brandBlock}
          initial={reduceMotion ? false : { opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .55 }}
        >
          <div className={styles.logoWrap}>
            <Image src="/icons/retail-mind-logo.png" alt="Retail Mind" width={110} height={110} priority className={styles.logo} />
          </div>
          <h1>Retail Mind</h1>
          <p>Shop Local</p>
          <p>Shop Smart</p>
        </motion.div>

        <motion.div
          className={styles.scene}
          aria-label="Illustration of a friendly local grocery store"
          initial={reduceMotion ? false : { opacity: 0, y: 10, scale: .97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: .65, delay: .08 }}
        >
          <img
            src="/illustrations/splash-local-market.svg"
            alt="A colourful neighbourhood shop with fresh produce and local shoppers"
            className={styles.sceneIllustration}
            loading="eager"
          />
          <span className={styles.sceneLabel}><Sparkles size={12} /> Your neighbourhood, one tap away</span>
          <span className={styles.floatBag}><ShoppingBag size={22} /></span>
          <span className={styles.floatLeaf}><Leaf size={22} /></span>
        </motion.div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.pageDots} aria-label="Welcome screen, 1 of 3">
          <span className={styles.dotActive} /><span /><span />
        </div>
        <Link href="/onboarding" className={styles.primaryButton}>
          Get Started <ArrowRight size={17} />
        </Link>
        <Link href="/" className={styles.secondaryLink}>Browse local shops instead</Link>
      </footer>
    </main>
  );
}
