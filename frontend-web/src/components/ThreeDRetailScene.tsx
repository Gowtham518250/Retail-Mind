'use client';

import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { Box, Package, Sparkles, ShoppingBag, Star, Store, Truck } from 'lucide-react';
import styles from './MarketplaceShell.module.css';

export default function ThreeDRetailScene() {
  const pointerX = useMotionValue(0);
  const pointerY = useMotionValue(0);
  const rotateY = useSpring(useTransform(pointerX, [-500, 500], [9, -9]), { stiffness: 120, damping: 18 });
  const rotateX = useSpring(useTransform(pointerY, [-300, 300], [-7, 7]), { stiffness: 120, damping: 18 });

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    pointerX.set(event.clientX - (rect.left + rect.width / 2));
    pointerY.set(event.clientY - (rect.top + rect.height / 2));
  };

  return (
    <motion.div
      className={styles.sceneWrap}
      onPointerMove={handlePointerMove}
      onPointerLeave={() => { pointerX.set(0); pointerY.set(0); }}
      style={{ perspective: 1400 }}
      aria-hidden="true"
    >
      <motion.div className={styles.scene} style={{ rotateX, rotateY }}>
        <div className={styles.sceneHalo} />
        <motion.div className={styles.orbit} animate={{ rotate: 360 }} transition={{ duration: 22, repeat: Infinity, ease: 'linear' }} />
        <motion.div className={styles.orbit + ' ' + styles.orbitTwo} animate={{ rotate: -360 }} transition={{ duration: 28, repeat: Infinity, ease: 'linear' }} />

        <div className={styles.platform}>
          <div className={styles.platformGrid} />
          <div className={styles.platformGlow} />
        </div>

        <motion.div className={styles.store3d} animate={{ y: [0, -10, 0], rotateZ: [-1, 1, -1] }} transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut' }}>
          <div className={styles.storeRoof} />
          <div className={styles.storeTopFace} />
          <div className={styles.storeFront}>
            <div className={styles.storeSign}><Store size={13} /> RETAIL MIND</div>
            <div className={styles.storeWindowRow}>
              <span><ShoppingBag size={18} /></span>
              <span><Package size={18} /></span>
              <span><Box size={18} /></span>
            </div>
            <div className={styles.storeCounter} />
            <div className={styles.storeDoor}><span /></div>
          </div>
          <div className={styles.storeSide} />
        </motion.div>

        <motion.div className={styles.floatingCard + ' ' + styles.cardOrders} animate={{ y: [0, -8, 0], rotateZ: [-2, 1, -2] }} transition={{ duration: 5.2, repeat: Infinity, ease: 'easeInOut' }}>
          <span className={styles.cardIconGreen}><Truck size={16} /></span>
          <span><strong>Fast delivery</strong><small>Track every order</small></span>
        </motion.div>

        <motion.div className={styles.floatingCard + ' ' + styles.cardAi} animate={{ y: [0, 10, 0], rotateZ: [2, -1, 2] }} transition={{ duration: 5.8, repeat: Infinity, ease: 'easeInOut', delay: .8 }}>
          <span className={styles.cardIconAmber}><Sparkles size={16} /></span>
          <span><strong>AI shopping</strong><small>Find smarter value</small></span>
        </motion.div>

        <motion.div className={styles.floatingCard + ' ' + styles.cardRating} animate={{ y: [0, -7, 0] }} transition={{ duration: 4.6, repeat: Infinity, ease: 'easeInOut', delay: .3 }}>
          <span className={styles.cardIconRose}><Star size={15} fill="currentColor" /></span>
          <span><strong>4.8 rated</strong><small>Trusted local shops</small></span>
        </motion.div>

        <motion.div className={styles.productPod + ' ' + styles.podOne} animate={{ y: [0, -12, 0], rotateY: [18, 26, 18] }} transition={{ duration: 5.6, repeat: Infinity, ease: 'easeInOut' }}>
          <div className={styles.podFace}><span>FRESH</span><strong>24/7</strong></div>
          <div className={styles.podTop} />
          <div className={styles.podSide} />
        </motion.div>

        <motion.div className={styles.productPod + ' ' + styles.podTwo} animate={{ y: [0, -8, 0], rotateY: [-20, -28, -20] }} transition={{ duration: 6.2, repeat: Infinity, ease: 'easeInOut', delay: 1 }}>
          <div className={styles.podFace}><span>BEST</span><strong>DEAL</strong></div>
          <div className={styles.podTop} />
          <div className={styles.podSide} />
        </motion.div>

        <div className={styles.ringLabel}><span /><strong>LIVE MARKETPLACE</strong></div>
      </motion.div>
    </motion.div>
  );
}
