'use client';

import { useEffect, useState } from 'react';
import { Capacitor } from '@capacitor/core';
import HeroScene3DFallback from './HeroScene3DFallback';
import type { HeroScene3DProps } from './HeroScene3DScene';

export default function HeroScene3D(props: HeroScene3DProps) {
  const [Scene, setScene] = useState<React.ComponentType<HeroScene3DProps> | null>(null);

  useEffect(() => {
    if (Capacitor.isNativePlatform()) return;

    let active = true;
    void import('./HeroScene3DScene')
      .then(({ default: HeroScene }) => {
        if (active) setScene(() => HeroScene);
      })
      .catch((error: unknown) => {
        console.error('Could not load the optional 3D hero scene.', error);
      });

    return () => {
      active = false;
    };
  }, []);

  if (Scene) return <Scene {...props} />;

  return (
    <div className={props.className}>
      <HeroScene3DFallback />
    </div>
  );
}
