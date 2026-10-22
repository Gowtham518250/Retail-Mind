'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ArrowRight, Apple, Carrot, Leaf, ShoppingBag, ShoppingBasket, Store, Trees } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import styles from './splash.module.css';

export default function SplashPage() {
  const reduceMotion = Boolean(useReducedMotion());

  return (
    <main className={styles.screen}>
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
          aria-label="Illustration of a neighbourhood store"
          initial={reduceMotion ? false : { opacity: 0, scale: .96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: .65, delay: .08 }}
        >
          <div className={styles.sun} />
          <div className={styles.cloud + ' ' + styles.cloudOne} />
          <div className={styles.cloud + ' ' + styles.cloudTwo} />
          <Trees className={styles.treeLeft} size={64} strokeWidth={1.45} />
          <Trees className={styles.treeRight} size={76} strokeWidth={1.45} />
          <div className={styles.storefront}>
            <div className={styles.storeRoof} />
            <div className={styles.storeSign}><Store size={15} /> YOUR NEIGHBOURHOOD STORE</div>
            <div className={styles.awning}>
              {Array.from({ length: 7 }).map((_, i) => <span key={i} className={i % 2 ? styles.awningBlue : styles.awningWhite} />)}
            </div>
            <div className={styles.shopBody}>
              <div className={styles.shopWindow}>
                <span className={styles.shelfLine} />
                <Apple size={21} />
                <Carrot size={22} />
                <Leaf size={21} />
                <span className={styles.shelfLine} />
              </div>
              <div className={styles.shopDoor}>
                <span className={styles.doorGlass} />
                <span className={styles.doorHandle} />
              </div>
              <div className={styles.shopWindow + ' ' + styles.rightWindow}>
                <span className={styles.shelfLine} />
                <ShoppingBasket size={22} />
                <Apple size={21} />
                <span className={styles.shelfLine} />
              </div>
            </div>
          </div>
          <div className={styles.walkway} />
          <span className={styles.floatBag}><ShoppingBag size={24} /></span>
          <span className={styles.floatLeaf}><Leaf size={24} /></span>
          <div className={styles.person + ' ' + styles.personOne}><span /><i /></div>
          <div className={styles.person + ' ' + styles.personTwo}><span /><i /></div>
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
