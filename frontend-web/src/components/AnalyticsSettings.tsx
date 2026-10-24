'use client';

import { GA_MEASUREMENT_ID, OPEN_ANALYTICS_SETTINGS_EVENT } from '../lib/analytics';

export default function AnalyticsSettings() {
  if (!GA_MEASUREMENT_ID) return null;

  return (
    <button
      type="button"
      className="site-footer-settings"
      onClick={() => window.dispatchEvent(new Event(OPEN_ANALYTICS_SETTINGS_EVENT))}
    >
      Analytics settings
    </button>
  );
}
