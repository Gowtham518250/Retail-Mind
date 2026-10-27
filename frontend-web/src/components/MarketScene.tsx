'use client';

import { motion, useReducedMotion } from 'framer-motion';

/**
 * Self-contained animated grocery scene (no remote images, works offline).
 * Produce pops out of the basket one after another, then floats; sparkles twinkle.
 * `compact` drops the halo/ground so it fits inside the home hero's own halo.
 */
const SPRING = { type: 'spring', stiffness: 170, damping: 13 } as const;
const BOX = { transformBox: 'fill-box', transformOrigin: 'center' } as const;

function Bob({ children, delay = 0, dy = 6, dur = 3.4, reduce }: { children: React.ReactNode; delay?: number; dy?: number; dur?: number; reduce: boolean }) {
  return (
    <motion.g
      style={BOX}
      animate={reduce ? undefined : { y: [0, -dy, 0], rotate: [-2, 2, -2] }}
      transition={{ duration: dur, delay, repeat: Infinity, ease: 'easeInOut' }}
    >
      {children}
    </motion.g>
  );
}

function Pop({ children, delay, reduce }: { children: React.ReactNode; delay: number; reduce: boolean }) {
  return (
    <motion.g
      style={BOX}
      initial={reduce ? false : { y: 70, scale: 0.2, opacity: 0 }}
      animate={{ y: 0, scale: 1, opacity: 1 }}
      transition={{ ...SPRING, delay }}
    >
      {children}
    </motion.g>
  );
}

function Sparkle({ x, y, s = 1, delay, reduce }: { x: number; y: number; s?: number; delay: number; reduce: boolean }) {
  return (
    <motion.path
      d="M0-10 L2.6-2.6 L10 0 L2.6 2.6 L0 10 L-2.6 2.6 L-10 0 L-2.6-2.6Z"
      fill="#fde68a"
      transform={`translate(${x} ${y}) scale(${s})`}
      style={BOX}
      animate={reduce ? { opacity: 0.8 } : { opacity: [0, 1, 0], scale: [0.4, 1.15, 0.4] }}
      transition={{ duration: 2.6, delay, repeat: Infinity, ease: 'easeInOut' }}
    />
  );
}

export default function MarketScene({ compact = false, className }: { compact?: boolean; className?: string }) {
  const reduce = Boolean(useReducedMotion());
  return (
    <svg
      viewBox="0 0 400 400"
      className={className}
      role="img"
      aria-label="A basket of fresh groceries"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <radialGradient id="ms-halo" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#4ade80" stopOpacity=".55" />
          <stop offset="60%" stopColor="#22c55e" stopOpacity=".18" />
          <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ms-basket" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#e9b872" />
          <stop offset="1" stopColor="#b7793a" />
        </linearGradient>
        <linearGradient id="ms-apple" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff6b5e" />
          <stop offset="1" stopColor="#d6322a" />
        </linearGradient>
        <linearGradient id="ms-orange" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ffc15a" />
          <stop offset="1" stopColor="#f08a16" />
        </linearGradient>
      </defs>

      {!compact && (
        <>
          <motion.circle cx="200" cy="205" r="175" fill="url(#ms-halo)"
            animate={reduce ? undefined : { scale: [1, 1.06, 1], opacity: [0.85, 1, 0.85] }}
            style={BOX} transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }} />
          <motion.circle cx="200" cy="205" r="150" fill="none" stroke="#86efac" strokeOpacity=".35" strokeWidth="1.5" strokeDasharray="3 9"
            animate={reduce ? undefined : { rotate: 360 }} style={BOX}
            transition={{ duration: 40, repeat: Infinity, ease: 'linear' }} />
          <motion.ellipse cx="200" cy="352" rx="95" ry="13" fill="#000" opacity=".28"
            animate={reduce ? undefined : { rx: [95, 80, 95], opacity: [0.28, 0.2, 0.28] }}
            transition={{ duration: 3.4, repeat: Infinity, ease: 'easeInOut' }} />
        </>
      )}

      <g transform={compact ? 'translate(0 -6) scale(1)' : undefined}>
        {/* handle sits behind the produce */}
        <Pop delay={0.2} reduce={reduce}>
          <path d="M104 232 C104 120 296 120 296 232" stroke="#9a6128" strokeWidth="9" fill="none" strokeLinecap="round" />
        </Pop>
        {/* produce, popping out behind the basket rim */}
        <Pop delay={0.55} reduce={reduce}>
          <Bob delay={0.2} reduce={reduce} dy={5}>
            <rect x="262" y="146" width="40" height="92" rx="14" fill="#f8fafc" />
            <rect x="262" y="146" width="40" height="30" rx="12" fill="#bfdbfe" />
            <rect x="271" y="132" width="22" height="18" rx="5" fill="#2563eb" />
          </Bob>
        </Pop>
        <Pop delay={0.7} reduce={reduce}>
          <Bob delay={0.5} reduce={reduce} dy={7} dur={3.9}>
            <path d="M118 238 C108 190 128 140 164 118 C168 160 160 205 148 238Z" fill="#22c55e" />
            <path d="M138 232 C140 190 150 160 164 118" stroke="#15803d" strokeWidth="3" fill="none" strokeLinecap="round" />
            <path d="M92 240 C90 200 108 168 132 154 C134 188 126 214 116 240Z" fill="#4ade80" />
          </Bob>
        </Pop>
        <Pop delay={0.85} reduce={reduce}>
          <Bob delay={0.9} reduce={reduce} dy={6} dur={3.1}>
            <circle cx="236" cy="196" r="36" fill="url(#ms-orange)" />
            <ellipse cx="224" cy="182" rx="10" ry="6" fill="#fff" opacity=".35" transform="rotate(-30 224 182)" />
            <path d="M236 160 q6 -10 16 -8 q-4 10 -16 8Z" fill="#16a34a" />
          </Bob>
        </Pop>
        <Pop delay={1.0} reduce={reduce}>
          <Bob delay={0.3} reduce={reduce} dy={8} dur={3.6}>
            <path d="M170 168 c-30 -18 -62 6 -52 46 c6 24 26 36 44 28 c8 -4 14 -4 22 0 c18 8 38 -4 44 -28 c10 -40 -22 -64 -52 -46 c-2 1 -4 1 -6 0Z" fill="url(#ms-apple)" />
            <ellipse cx="146" cy="196" rx="9" ry="14" fill="#fff" opacity=".28" transform="rotate(18 146 196)" />
            <path d="M176 166 q2 -18 14 -26" stroke="#7c4a1d" strokeWidth="5" fill="none" strokeLinecap="round" />
            <path d="M190 148 q16 -14 30 -4 q-12 14 -30 4Z" fill="#22c55e" />
          </Bob>
        </Pop>

        {/* basket */}
        <Pop delay={0.2} reduce={reduce}>
          <path d="M84 232 Q200 214 316 232 L292 336 Q200 352 108 336Z" fill="url(#ms-basket)" />
          <g stroke="#8a5424" strokeOpacity=".45" strokeWidth="3" strokeLinecap="round" fill="none">
            <path d="M96 262 Q200 248 304 262" />
            <path d="M102 292 Q200 278 298 292" />
            <path d="M108 320 Q200 306 292 320" />
            <path d="M140 238 L132 338" /><path d="M176 236 L170 344" />
            <path d="M212 236 L214 344" /><path d="M250 238 L258 340" />
          </g>
          <path d="M78 232 Q200 208 322 232 Q322 244 312 246 Q200 230 88 246 Q78 244 78 232Z" fill="#f3c98a" />
        </Pop>
      </g>

      <Sparkle x={86} y={118} s={1.1} delay={1.2} reduce={reduce} />
      <Sparkle x={322} y={96} s={0.8} delay={1.9} reduce={reduce} />
      <Sparkle x={338} y={236} s={0.9} delay={2.4} reduce={reduce} />
      <Sparkle x={62} y={250} s={0.7} delay={0.6} reduce={reduce} />
    </svg>
  );
}
