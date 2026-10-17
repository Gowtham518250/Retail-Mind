'use client';

import { useEffect } from 'react';
import { Capacitor } from '@capacitor/core';

export default function NativeAppPerformance() {
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;

    document.documentElement.dataset.nativeApp = 'true';
    return () => {
      delete document.documentElement.dataset.nativeApp;
    };
  }, []);

  return null;
}
