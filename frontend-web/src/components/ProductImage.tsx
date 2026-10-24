'use client';

import { useEffect, useState } from 'react';
import { lookupProductImage, resolveImageUrl } from '../lib/productImage';
import styles from './ProductImage.module.css';

interface ProductImageProps {
  /** Photo the shopkeeper uploaded (may be empty or broken). */
  src?: string | null;
  name?: string;
  productName?: string;
  category?: string;
  className?: string;
  eager?: boolean;
  alt?: string;
  width?: number;
  height?: number;
  sizes?: string;
  /** Called with the final URL being shown (handy for the fly-to-cart animation). */
  onResolved?: (url: string | null) => void;
}

type Stage = 'own' | 'lookup' | 'web' | 'fallback';

/**
 * Prioritizes the shopkeeper's uploaded photo first.
 * If the shopkeeper didn't upload an image (or if their upload fails to load),
 * it queries our online photo lookup for a real, high-quality product photo.
 */
export default function ProductImage({
  src,
  name,
  productName,
  category,
  className = '',
  eager,
  alt,
  onResolved,
}: ProductImageProps) {
  const actualName = (name || productName || '').trim();
  const own = resolveImageUrl(src);
  const [stage, setStage] = useState<Stage>(own ? 'own' : 'lookup');
  const [web, setWeb] = useState<string | null>(null);
  const [imgLoaded, setImgLoaded] = useState(false);

  useEffect(() => {
    setStage(own ? 'own' : 'lookup');
    setWeb(null);
    setImgLoaded(false);
  }, [own, actualName]);

  useEffect(() => {
    if (stage !== 'lookup') return;
    let cancelled = false;
    lookupProductImage(actualName, category).then((url) => {
      if (cancelled) return;
      if (url) {
        setWeb(url);
        setStage('web');
      } else {
        setStage('fallback');
      }
    });
    return () => {
      cancelled = true;
    };
  }, [stage, actualName, category]);

  useEffect(() => {
    onResolved?.(stage === 'own' ? own : stage === 'web' ? web : null);
  }, [stage, own, web, onResolved]);

  const activeUrl = stage === 'own' ? own : stage === 'web' ? web : null;

  return (
    <div className={`${styles.wrapper} ${className}`}>
      {activeUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={activeUrl}
          src={activeUrl}
          alt={alt || actualName}
          className={`${styles.img} ${stage === 'own' ? styles.own : styles.web}`}
          data-source={stage === 'own' ? 'shopkeeper' : 'online'}
          loading={eager ? 'eager' : 'lazy'}
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setImgLoaded(true)}
          onError={() => {
            // If the shopkeeper's image fails to load, gracefully fall back to online photo lookup
            if (stage === 'own') {
              setStage('lookup');
            } else {
              setStage('fallback');
            }
          }}
        />
      ) : null}

      {(!imgLoaded || stage === 'lookup') && (
        <div className={styles.skeleton} aria-hidden="true">
          {stage === 'fallback' && (
            <span className={styles.fallbackLetter}>
              {actualName.trim().charAt(0).toUpperCase() || '·'}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
