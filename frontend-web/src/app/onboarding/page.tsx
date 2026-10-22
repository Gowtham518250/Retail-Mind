'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Apple, ArrowRight, CheckCircle2, ChevronLeft, ChevronRight, Leaf, MapPin, ShieldCheck, ShoppingBasket, Sparkles, Truck } from 'lucide-react';
import { motion, useReducedMotion } from 'framer-motion';
import styles from './onboarding.module.css';

const slides = [
  {
    eyebrow: 'WELCOME TO RETAIL MIND',
    title: <>Everything You Need<br />From <span>Local Shops</span></>,
    description: 'Fresh groceries, daily essentials, and more from nearby shops.',
    feature: 'One simple place for your everyday needs',
    icon: ShoppingBasket,
    tone: 'blue',
  },
  {
    eyebrow: 'FRESH PICKS, CLOSE BY',
    title: <>Good Things.<br /><span>Close to Home.</span></>,
    description: 'Discover neighbourhood stores and browse what they have available.',
    feature: 'Explore products from local favourites',
    icon: Apple,
    tone: 'green',
  },
  {
    eyebrow: 'SIMPLE FROM START TO DOOR',
    title: <>Shopping Made<br /><span>Easy for You.</span></>,
    description: 'Keep your cart together, place your order, and follow its progress.',
    feature: 'Clear checkout and order updates',
    icon: Truck,
    tone: 'violet',
  },
];

export default function OnboardingPage() {
  const [active, setActive] = useState(0);
  const reduceMotion = Boolean(useReducedMotion());
  const slide = slides[active];
  const Icon = slide.icon;

  const previous = () => setActive((current) => (current + slides.length - 1) % slides.length);
  const next = () => setActive((current) => (current + 1) % slides.length);

  return (
    <main className={styles.screen}>
      <header className={styles.header}>
        <Link href="/splash" className={styles.backButton} aria-label="Back to splash screen">
          <ChevronLeft size={20} />
        </Link>
        <div className={styles.stepLabel}>GET TO KNOW US <b>{active + 1} / {slides.length}</b></div>
        <Link href="/auth" className={styles.skipLink}>Skip</Link>
      </header>

      <section className={styles.content} aria-live="polite">
        <motion.div
          className={styles.illustration}
          key={'illustration-' + active}
          initial={reduceMotion ? false : { opacity: 0, y: 8, scale: .97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: .28 }}
        >
          <div className={styles.halo} />
          <span className={styles.sparkleOne}><Sparkles size={18} /></span>
          <span className={styles.sparkleTwo}><Leaf size={20} /></span>
          <div className={styles.heroProductCard}>
            <div className={styles.productHead}><span /> <span /> <span /></div>
            <div className={styles.productArt}>
              <div className={styles.blueCart}><Icon size={84} strokeWidth={1.55} /></div>
              <div className={styles.floatingProduct + ' ' + styles.productOne}><Apple size={28} /></div>
              <div className={styles.floatingProduct + ' ' + styles.productTwo}><Leaf size={29} /></div>
              <div className={styles.floatingProduct + ' ' + styles.productThree}><ShoppingBasket size={25} /></div>
            </div>
            <div className={styles.fakeLines}><span /><span /><i /></div>
          </div>
          <div className={styles.smallCard + ' ' + styles.nearbyCard}>
            <span className={styles.smallCardIcon}><MapPin size={14} /></span>
            <span><b>Nearby shops</b><small>Ready for you</small></span>
            <CheckCircle2 size={15} className={styles.check} />
          </div>
          <div className={styles.smallCard + ' ' + styles.freshCard}>
            <span className={styles.smallCardIcon + ' ' + styles.freshIcon}><ShieldCheck size={14} /></span>
            <span><b>Fresh & local</b><small>Everyday essentials</small></span>
          </div>
        </motion.div>

        <motion.div
          className={styles.copy}
          key={'copy-' + active}
          initial={reduceMotion ? false : { opacity: 0, y: 7 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .25 }}
        >
          <span className={styles.eyebrow}>{slide.eyebrow}</span>
          <h1>{slide.title}</h1>
          <p>{slide.description}</p>
          <div className={styles.feature}><span><CheckCircle2 size={15} /></span>{slide.feature}</div>
        </motion.div>
      </section>

      <footer className={styles.footer}>
        <div className={styles.carouselControls}>
          <button type="button" onClick={previous} className={styles.arrowButton} aria-label="Previous onboarding slide">
            <ChevronLeft size={18} />
          </button>
          <div className={styles.dots} role="group" aria-label="Choose onboarding slide">
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
          <button type="button" onClick={next} className={styles.arrowButton} aria-label="Next onboarding slide">
            <ChevronRight size={18} />
          </button>
        </div>
        <Link href="/auth?view=register" className={styles.primaryButton}>
          Get Started <ArrowRight size={17} />
        </Link>
        <p className={styles.signInPrompt}>Already have an account? <Link href="/auth">Sign in</Link></p>
        <p className={styles.footerTrust}><ShieldCheck size={13} /> Shop local. Shop smart.</p>
      </footer>
    </main>
  );
}
