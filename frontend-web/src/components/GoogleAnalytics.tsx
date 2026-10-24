'use client';

import Link from 'next/link';
import Script from 'next/script';
import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import {
  GA_MEASUREMENT_ID,
  OPEN_ANALYTICS_SETTINGS_EVENT,
  readAnalyticsConsent,
  trackPageView,
  writeAnalyticsConsent,
  type AnalyticsConsent,
} from '../lib/analytics';
import styles from './AnalyticsConsent.module.css';

export default function GoogleAnalytics() {
  const pathname = usePathname();
  const [consent, setConsent] = useState<AnalyticsConsent | 'unset'>('unset');
  const [bannerOpen, setBannerOpen] = useState(false);
  const [tagReady, setTagReady] = useState(false);
  const lastPageRef = useRef('');

  useEffect(() => {
    if (!GA_MEASUREMENT_ID) return;
    const saved = readAnalyticsConsent();
    setConsent(saved ?? 'unset');
    setBannerOpen(saved === null);

    const openSettings = () => setBannerOpen(true);
    window.addEventListener(OPEN_ANALYTICS_SETTINGS_EVENT, openSettings);
    return () => window.removeEventListener(OPEN_ANALYTICS_SETTINGS_EVENT, openSettings);
  }, []);

  useEffect(() => {
    if (!GA_MEASUREMENT_ID || consent !== 'granted' || !tagReady) return;
    if (lastPageRef.current === pathname) return;
    lastPageRef.current = pathname;
    trackPageView(pathname, document.title);
  }, [consent, pathname, tagReady]);

  const chooseConsent = (value: AnalyticsConsent) => {
    writeAnalyticsConsent(value);
    setConsent(value);
    setBannerOpen(false);

    if (GA_MEASUREMENT_ID) {
      const disableKey = `ga-disable-${GA_MEASUREMENT_ID}`;
      (window as unknown as Record<string, boolean>)[disableKey] = value === 'denied';
      if (value === 'granted') {
        lastPageRef.current = '';
        setTagReady(Boolean(window.gtag));
      }

      try {
        window.gtag?.('consent', 'update', { analytics_storage: value });
      } catch {
        // The page must remain usable if analytics is blocked by the browser.
      }
    }
  };

  if (!GA_MEASUREMENT_ID) return null;

  return (
    <>
      {consent === 'granted' && (
        <>
          <Script
            id="retail-mind-ga4"
            src={`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(GA_MEASUREMENT_ID)}`}
            strategy="afterInteractive"
            onReady={() => setTagReady(true)}
          />
          <Script id="retail-mind-ga4-config" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              window.gtag = function () { window.dataLayer.push(arguments); };
              window.gtag('js', new Date());
              window.gtag('consent', 'default', {
                analytics_storage: 'granted',
                ad_storage: 'denied',
                ad_user_data: 'denied',
                ad_personalization: 'denied'
              });
              window.gtag('config', '${GA_MEASUREMENT_ID}', {
                send_page_view: false,
                anonymize_ip: true,
                allow_google_signals: false,
                allow_ad_personalization_signals: false
              });
            `}
          </Script>
        </>
      )}

      {bannerOpen && (
        <section className={styles.banner} aria-label="Analytics consent">
          <div className={styles.copy}>
            <strong>Help us improve Retail Mind</strong>
            <p>
              With your permission we use Google Analytics to understand which public pages are useful.
              We do not send account details, cart contents, checkout details, or passwords. Read our{' '}
              <Link href="/privacy">privacy information</Link>.
            </p>
          </div>
          <div className={styles.actions}>
            <button type="button" className={styles.decline} onClick={() => chooseConsent('denied')}>
              Decline
            </button>
            <button type="button" className={styles.accept} onClick={() => chooseConsent('granted')}>
              Allow analytics
            </button>
          </div>
        </section>
      )}
    </>
  );
}
