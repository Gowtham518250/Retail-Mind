'use client';

import { motion, useReducedMotion, type Variants } from 'framer-motion';

const EASE = [0.16, 1, 0.3, 1] as const;

interface RevealProps {
  children: React.ReactNode;
  className?: string;
  /** Delay in seconds. */
  delay?: number;
  /** Start offset in px (positive = rises from below). */
  y?: number;
  /** Optional horizontal start offset in px. */
  x?: number;
  as?: 'div' | 'section' | 'span' | 'li' | 'article';
  id?: string;
  'aria-label'?: string;
  'aria-labelledby'?: string;
}

/** Fades + rises into view once, the first time it scrolls on screen. */
export function Reveal({ children, className, delay = 0, y = 28, x = 0, as = 'div', id, ...aria }: RevealProps) {
  const reduce = Boolean(useReducedMotion());
  const Tag = motion[as];
  return (
    <Tag
      id={id}
      {...aria}
      className={className}
      initial={reduce ? false : { opacity: 0, y, x, filter: 'blur(8px)' }}
      whileInView={{ opacity: 1, y: 0, x: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: reduce ? 0 : 0.62, delay, ease: EASE }}
    >
      {children}
    </Tag>
  );
}

const container = (stagger: number, delayChildren: number): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: stagger, delayChildren } },
});

const item: Variants = {
  hidden: { opacity: 0, y: 28, scale: 0.94, filter: 'blur(6px)' },
  show: { opacity: 1, y: 0, scale: 1, filter: 'blur(0px)', transition: { duration: 0.58, ease: EASE } },
};

interface StaggerProps {
  children: React.ReactNode;
  className?: string;
  stagger?: number;
  delay?: number;
}

/** Wrap a grid; each <StaggerItem> inside animates in one after another. */
export function Stagger({ children, className, stagger = 0.07, delay = 0 }: StaggerProps) {
  const reduce = Boolean(useReducedMotion());
  return (
    <motion.div
      className={className}
      variants={container(reduce ? 0 : stagger, delay)}
      initial={reduce ? 'show' : 'hidden'}
      whileInView="show"
      viewport={{ once: true, margin: '-40px' }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerItem({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduce = Boolean(useReducedMotion());
  return (
    <motion.div className={className} variants={reduce ? undefined : item}>
      {children}
    </motion.div>
  );
}

/** Splits a headline into words that slide up one by one on mount. */
export function WordReveal({ text, className, delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduce = Boolean(useReducedMotion());
  const words = text.split(' ');
  return (
    <span className={className} aria-label={text}>
      {words.map((word, i) => (
        <span key={i} aria-hidden="true" style={{ display: 'inline-block', overflow: 'hidden', verticalAlign: 'bottom', paddingBottom: '.12em', marginBottom: '-.12em' }}>
          <motion.span
            style={{ display: 'inline-block' }}
            initial={reduce ? false : { y: '110%', rotate: 4 }}
            animate={{ y: 0, rotate: 0 }}
            transition={{ duration: 0.8, delay: delay + i * 0.07, ease: EASE }}
          >
            {word}{i < words.length - 1 ? ' ' : ''}
          </motion.span>
        </span>
      ))}
    </span>
  );
}
