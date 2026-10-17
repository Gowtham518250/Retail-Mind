import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.retailmind.customer',
  appName: 'RetailMind',
  webDir: 'out',
  server: {
    url: process.env.CAPACITOR_SERVER_URL || 'https://retail-mind-1.onrender.com',
    cleartext: false,
    androidScheme: 'https',
  },
};

export default config;
