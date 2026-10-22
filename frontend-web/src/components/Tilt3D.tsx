'use client';

import { useRef } from 'react';
import { motion, useMotionTemplate, useMotionValue, useReducedMotion, useSpring, useTransform } from 'framer-motion';
import styles from './Tilt3D.module.css';

interface Tilt3DProps {
  children: React.ReactNode;
  className?: string;
  /** Maximum rotation in degrees. */
  max?: number;
  /** Lift towards the viewer on hover, in px. */
  lift?: number;
}

/**
 * Wraps content in a perspective container that tilts towards the pointer and
 * paints a moving highlight. Children can use `transform: translateZ()` to
 * sit on different depth layers (the wrapper preserves 3D).
 * Touch input and reduced-motion users get a static element.
 */
export default function Tilt3D({ children, className, max = 1.8, lift = 1.2 }: Tilt3DProps) {
  const reduce = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const hover = useMotionValue(0);

  const spring = { stiffness: 260, damping: 30, mass: 0.55 };
  const rotateY = useSpring(useTransform(px, [0, 1], [-max, max]), spring);
  const rotateX = useSpring(useTransform(py, [0, 1], [max, -max]), spring);
  const z = useSpring(useTransform(hover, [0, 1], [0, lift]), spring);

  const gx = useTransform(px, (v) => `${v * 100}%`);
  const gy = useTransform(py, (v) => `${v * 100}%`);
  const glare = useMotionTemplate`radial-gradient(420px circle at ${gx} ${gy}, rgba(255,255,255,0.16), transparent 52%)`;
  const glareOpacity = useSpring(hover, { stiffness: 140, damping: 20 });

  if (reduce) return <div className={className}>{children}</div>;

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.pointerType === 'touch' || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
    hover.set(1);
  };
  const onLeave = () => {
    px.set(0.5);
    py.set(0.5);
    hover.set(0);
  };

  return (
    <motion.div
      ref={ref}
      className={`${styles.tilt} ${className || ''}`}
      style={{ rotateX, rotateY, z, transformPerspective: 1000, transformStyle: 'preserve-3d' }}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
    >
      {children}
      <motion.span aria-hidden="true" className={styles.glare} style={{ background: glare, opacity: glareOpacity }} />
    </motion.div>
  );
}
