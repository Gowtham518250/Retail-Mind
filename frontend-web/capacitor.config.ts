import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.retailmind.customer',
  appName: 'RetailMind',
  webDir: 'out',
  server: {
    // If CAPACITOR_SERVER_URL is provided, load the live deployed URL (e.g. Render / custom domain)
    // Otherwise it defaults to local assets
    url: process.env.CAPACITOR_SERVER_URL || undefined,
    cleartext: true,
    androidScheme: 'https',
  },
};

export default config;

