'use client';

import { motion, useReducedMotion, useScroll, useSpring } from 'framer-motion';

/** Thin brand-coloured reading-progress bar pinned under the status bar. */
export default function ScrollProgress() {
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 140, damping: 28, mass: 0.4 });
  if (reduce) return null;
  return <motion.div aria-hidden="true" className="rm-scroll-progress" style={{ scaleX }} />;
}
