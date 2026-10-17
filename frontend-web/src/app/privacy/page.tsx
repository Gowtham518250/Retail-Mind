import type { Metadata } from 'next';
import { publicPageMetadata } from '../../lib/seo';

export const metadata: Metadata = publicPageMetadata({
  title: 'Privacy | Retail Mind',
  description: 'Learn how Retail Mind uses account and order information to provide its customer shopping experience.',
  path: '/privacy',
});

export default function PrivacyPage() {
  return (
    <main className="container" style={{ maxWidth: 880, paddingBlock: 'clamp(40px, 8vw, 88px)' }}>
      <p className="section-eyebrow">Retail Mind</p>
      <h1>Privacy information</h1>
      <p>
        This page summarizes information handled by the Retail Mind customer website. The service operator
        should review and complete this notice with verified retention periods and support contact details
        before relying on it as a formal privacy policy.
      </p>
      <h2>Account and order information</h2>
      <p>
        Creating an account can involve a name, email address, and phone number. Placing an order can
        involve contact details, delivery instructions, selected products, and order status. These details
        are sent to the Retail Mind service and the selected shop to support account and order workflows.
      </p>
      <h2>Authentication and device storage</h2>
      <p>
        The customer app stores an authentication token in browser local storage after sign-in. Anyone
        using a shared device should sign out when finished. Do not share passwords or verification codes.
      </p>
      <h2>Payments and third-party services</h2>
      <p>
        The app can display cash and UPI order options. This page does not assert that Retail Mind itself
        processes card or bank payments. The app communicates with its configured Retail Mind backend;
        shop and service providers may handle information under their own practices.
      </p>
      <h2>Analytics, cookies, and retention</h2>
      <p>
        No Google Analytics measurement ID is configured in this frontend. The service operator should
        document any production analytics, cookies, logs, retention periods, deletion requests, and
        applicable user rights before launch.
      </p>
      <h2>Questions</h2>
      <p>
        Contact and privacy-request details have not been provided in the application configuration.
        The service operator should publish a verified support channel before launch.
      </p>
    </main>
  );
}
