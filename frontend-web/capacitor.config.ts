import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.retailmind.customer',
  appName: 'RetailMind',
  webDir: 'out',
  server: {
    // Set to the deployed customer website; the retail API URL is configured separately.
    url: process.env.CAPACITOR_SERVER_URL || undefined,
    cleartext: true,
    androidScheme: 'https',
  },
};

export default config;
