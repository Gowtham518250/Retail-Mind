'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Zap,
  Store,
  MapPin,
  Sparkles,
} from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import styles from './onboarding.module.css';

const slides = [
  {
    eyebrow: 'FRESH EVERY DAY',
    title: (
      <>
        Everything You Need<br />From <span>Local Shops</span>
      </>
    ),
    description: 'Farm-fresh vegetables, dairy, pantry staples, and everyday essentials from your trusted neighbourhood grocers.',
    feature: '100% authentic goods from verified shops',
    photo: 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=800&q=80',
    photoAlt: 'Fresh organic groceries and produce basket',
    badgeOne: { icon: Zap, label: 'Fast Delivery', sub: '15-30 mins' },
    badgeTwo: { icon: ShieldCheck, label: 'Quality Checked', sub: 'Fresh daily' },
  },
  {
    eyebrow: 'COMMUNITY FIRST',
    title: (
      <>
        Your Favourite Stores,<br /><span>Right In Your Pocket.</span>
      </>
    ),
    description: 'Explore verified corner shops, supermarkets, and specialty merchants in your area with live inventory and transparent pricing.',
    feature: 'Real-time shelf availability & local prices',
    photo: 'https://images.unsplash.com/photo-1578916171728-46686eac8d58?auto=format&fit=crop&w=800&q=80',
    photoAlt: 'Neighbourhood grocery and marketplace store',
    badgeOne: { icon: Store, label: '50+ Local Shops', sub: 'In your area' },
    badgeTwo: { icon: MapPin, label: 'Hyperlocal', sub: 'Near your home' },
  },
  {
    eyebrow: 'SIMPLE & RELIABLE',
    title: (
      <>
        From Shop Shelf<br /><span>To Your Doorstep.</span>
      </>
    ),
    description: 'Add items from multiple local aisles, place your order seamlessly, and follow its progress until it reaches your door.',
    feature: 'Transparent checkout & live order tracking',
    photo: 'https://images.unsplash.com/photo-1616401784845-180882ba9ba8?auto=format&fit=crop&w=800&q=80',
    photoAlt: 'Carefully packed grocery delivery at the doorstep',
    badgeOne: { icon: Sparkles, label: 'Easy Checkout', sub: 'UPI & Cards' },
    badgeTwo: { icon: ShieldCheck, label: 'Order Security', sub: 'Guaranteed' },
  },
];

export default function OnboardingPage() {
  useEffect(() => {
    try {
      window.localStorage.setItem('retailMindIntroSeen', '1');
    } catch {
      /* optional preference */
    }
  }, []);

  const [active, setActive] = useState(0);
  const reduceMotion = Boolean(useReducedMotion());
  const slide = slides[active];

  const previous = () => setActive((current) => (current + slides.length - 1) % slides.length);
  const next = () => setActive((current) => (current + 1) % slides.length);

  return (
    <main className={styles.screen} data-entry-screen="onboarding">
      <div className={styles.ambientTop} aria-hidden="true" />
      <div className={styles.ambientBottom} aria-hidden="true" />

      <header className={styles.header}>
        <Link href="/splash" className={styles.backButton} aria-label="Back to splash screen">
          <ChevronLeft size={20} />
        </Link>
        <div className={styles.stepIndicator}>
          <span>EXPERIENCE</span>
          <b>{active + 1} / {slides.length}</b>
        </div>
        <Link href="/auth" className={styles.skipLink}>Skip</Link>
      </header>

      <section className={styles.content} aria-live="polite">
        <motion.div
          className={styles.visualCard}
          key={'photo-' + active}
          initial={reduceMotion ? false : { opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.35 }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={slide.photo}
            alt={slide.photoAlt}
            className={styles.visualImage}
            loading="eager"
          />
          <div className={styles.visualOverlay} />

          {/* Floating Pill Badges */}
          <div className={`${styles.floatingBadge} ${styles.badgeLeft}`}>
            <span className={styles.floatingIcon}>
              <slide.badgeOne.icon size={15} />
            </span>
            <div>
              <strong>{slide.badgeOne.label}</strong>
              <small>{slide.badgeOne.sub}</small>
            </div>
          </div>

          <div className={`${styles.floatingBadge} ${styles.badgeRight}`}>
            <span className={`${styles.floatingIcon} ${styles.iconGreen}`}>
              <slide.badgeTwo.icon size={15} />
            </span>
            <div>
              <strong>{slide.badgeTwo.label}</strong>
              <small>{slide.badgeTwo.sub}</small>
            </div>
          </div>
        </motion.div>

        <motion.div
          className={styles.copy}
          key={'copy-' + active}
          initial={reduceMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={reduceMotion ? { duration: 0 } : { duration: 0.3 }}
        >
          <span className={styles.eyebrow}>{slide.eyebrow}</span>
          <h1>{slide.title}</h1>
          <p>{slide.description}</p>
          <div className={styles.featurePill}>
            <CheckCircle2 size={16} className={styles.featureCheck} />
            <span>{slide.feature}</span>
          </div>
        </motion.div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.carouselControls}>
          <button
            type="button"
            onClick={previous}
            className={styles.arrowButton}
            aria-label="Previous slide"
          >
            <ChevronLeft size={18} />
          </button>
          <div className={styles.dots} role="group" aria-label="Onboarding slides">
            {slides.map((item, index) => (
              <button
                key={item.eyebrow}
                type="button"
                aria-label={'Slide ' + (index + 1)}
                aria-current={active === index ? 'step' : undefined}
                className={active === index ? styles.dotActive : styles.dot}
                onClick={() => setActive(index)}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={next}
            className={styles.arrowButton}
            aria-label="Next slide"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        <Link href="/auth?view=register" className={styles.primaryButton}>
          <span>Get Started</span>
          <ArrowRight size={18} />
        </Link>

        <div className={styles.footerMeta}>
          <span className={styles.signInPrompt}>
            Already have an account? <Link href="/auth">Sign in</Link>
          </span>
          <span className={styles.footerTrust}>
            <ShieldCheck size={14} /> Shop Local. Shop Smart.
          </span>
        </div>
      </footer>
    </main>
  );
}
