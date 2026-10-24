'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { Capacitor } from '@capacitor/core';
import { MotionConfig } from 'framer-motion';

export default function NativeAppPerformance({ children }: { children: ReactNode }) {
  const [native, setNative] = useState(false);

  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    document.documentElement.dataset.nativeApp = 'true';
    setNative(true);
    return () => {
      delete document.documentElement.dataset.nativeApp;
    };
  }, []);

  if (!native) return children;
  return <MotionConfig reducedMotion="always">{children}</MotionConfig>;
}
