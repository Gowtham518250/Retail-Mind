import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '../../components/JsonLd';
import { GA_MEASUREMENT_ID } from '../../lib/analytics';
import { absoluteSiteUrl, publicPageMetadata } from '../../lib/seo';
import { SUPPORT_EMAIL } from '../../lib/support';
import styles from './privacy.module.css';

export const metadata: Metadata = publicPageMetadata({
  title: 'Privacy | Retail Mind',
  description: 'How Retail Mind handles account, order, authentication, and optional analytics information on the customer website.',
  path: '/privacy',
});

export default function PrivacyPage() {
  return (
    <main className={`container ${styles.page}`} data-experience="privacy">
      <JsonLd data={{
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
          { '@type': 'ListItem', position: 2, name: 'Privacy', item: absoluteSiteUrl('/privacy') },
        ],
      }} />
      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Privacy</span>
      </nav>

      <header className={styles.header}>
        <p className="section-eyebrow">Retail Mind</p>
        <h1>Privacy information</h1>
        <p>
          This notice describes the information handled by the Retail Mind customer website. It is an
          implementation summary, not a legal-reviewed policy. The service operator must confirm retention
          periods, user rights, and support details before relying on it as a formal privacy notice.
        </p>
        <p className={styles.updated}>Last updated: 18 October 2026</p>
      </header>

      <article className={styles.prose}>
        <section aria-labelledby="privacy-account">
          <h2 id="privacy-account">Account and order information</h2>
          <p>
            Creating an account can involve a name, email address, and phone number. Placing an order can
            involve contact details, delivery instructions, selected products, order value, and order status.
            These details are sent to the Retail Mind service and the selected shop so they can provide
            account and order workflows.
          </p>
          <p>
            Checkout stores a short-lived idempotency key in session storage to prevent accidental duplicate
            orders. Order confirmation details may also be kept in session storage for the confirmation page.
          </p>
        </section>

        <section aria-labelledby="privacy-device">
          <h2 id="privacy-device">Authentication and device storage</h2>
          <p>
            After sign-in, the customer app stores an authentication token, name, and email address in
            browser local storage. The shopping cart is stored locally so it survives a page refresh. This
            information is not shared with other customers by the frontend. Anyone using a shared device
            should sign out when finished.
          </p>
          <p>
            Do not send passwords, one-time codes, access tokens, or payment credentials in messages to
            Retail Mind or a shop.
          </p>
        </section>

        <section aria-labelledby="privacy-payments">
          <h2 id="privacy-payments">Payments and third-party services</h2>
          <p>
            Checkout displays the payment options the selected shop has enabled. The customer website does
            not collect card numbers or bank credentials. The Retail Mind backend, hosting provider, email
            provider, and the selected shop may process information needed to operate the service under
            their own practices.
          </p>
          <p>
            If you use the optional location button at checkout, your browser sends coordinates to
            OpenStreetMap&apos;s Nominatim service to look up an address. Do not use that button if you do not
            want to share your device location with that service.
          </p>
        </section>

        <section aria-labelledby="privacy-analytics">
          <h2 id="privacy-analytics">Analytics and cookies</h2>
          <p>The customer website also requests Google Fonts from Google to display its typefaces. That request shares your IP address and user agent with Google; no account or order information is included. The operator should confirm this third-party dependency during legal review.</p>
          {GA_MEASUREMENT_ID ? (
            <>
              <p>
                Google Analytics 4 is configured for this website. It loads only after you choose{' '}
                <strong>Allow analytics</strong> in the consent banner. We send public page views, shop and
                product views, and search activity. We configure analytics to avoid advertising storage and
                Google signals, and we do not send account details, cart contents, checkout details, or
                passwords.
              </p>
              <p>
                You can change or withdraw your analytics choice at any time using the&nbsp;
                <strong>Analytics settings</strong> link in the footer. Declining analytics does not prevent
                you from browsing, signing in, or ordering.
              </p>
            </>
          ) : (
            <p>
              No Google Analytics measurement ID is configured for this website, so the GA4 integration
              remains inactive. The service operator should document any production cookies, logs, and
              analytics before enabling them.
            </p>
          )}
        </section>

        <section aria-labelledby="privacy-retention">
          <h2 id="privacy-retention">Retention, deletion, and your choices</h2>
          <p>
            The application does not currently expose a self-service account-deletion or data-export
            workflow. Retention periods are set by the service operator and are not stated here because they
            have not been verified in this repository. You can clear the local cart and sign out from the
            customer account on a shared device.
          </p>
          <p>
            For an order, shop, privacy, or accessibility question, use the{' '}
            <Link href="/contact">contact page</Link>. Do not include passwords, one-time codes, or payment
            credentials.
          </p>
        </section>

        <section aria-labelledby="privacy-contact">
          <h2 id="privacy-contact">Contact</h2>
          {SUPPORT_EMAIL ? (
            <p>
              A verified support channel is configured at{' '}
              <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>. Use it for privacy requests and
              account questions. The{' '}
              <Link href="/contact">contact page</Link> can prepare an email in your own email app.
            </p>
          ) : (
            <p>
              A verified privacy or support contact has not been configured for this website. The service
              operator must publish a real support channel before launch; the{' '}
              <Link href="/contact">contact page</Link> explains the current limitations.
            </p>
          )}
        </section>
      </article>
    </main>
  );
}
