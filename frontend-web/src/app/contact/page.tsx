import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '../../components/JsonLd';
import ContactForm from '../../components/ContactForm';
import { absoluteSiteUrl, publicPageMetadata, SITE_NAME } from '../../lib/seo';
import { SUPPORT_EMAIL } from '../../lib/support';
import styles from './contact.module.css';

export const metadata: Metadata = {
  ...publicPageMetadata({
    title: 'Contact | Retail Mind',
    description: 'Contact Retail Mind about an order, a shop, accessibility, privacy, or using the customer website.',
    path: '/contact',
  }),
  ...(SUPPORT_EMAIL ? {} : { robots: { index: false, follow: true } }),
};

export default function ContactPage() {
  const breadcrumbJsonLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      { '@type': 'ListItem', position: 1, name: 'Home', item: absoluteSiteUrl('/') },
      { '@type': 'ListItem', position: 2, name: 'Contact', item: absoluteSiteUrl('/contact') },
    ],
  };

  return (
    <main className={`container ${styles.page}`} data-experience="contact">
      <JsonLd data={breadcrumbJsonLd} />
      {SUPPORT_EMAIL && (
        <JsonLd data={{
          '@context': 'https://schema.org',
          '@type': 'ContactPage',
          name: `Contact ${SITE_NAME}`,
          url: absoluteSiteUrl('/contact'),
          mainEntity: {
            '@type': 'Organization',
            name: SITE_NAME,
            url: absoluteSiteUrl('/'),
            contactPoint: {
              '@type': 'ContactPoint',
              contactType: 'customer support',
              email: SUPPORT_EMAIL,
            },
          },
        }} />
      )}

      <nav aria-label="Breadcrumb" className={styles.breadcrumb}>
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">Contact</span>
      </nav>

      <header className={styles.header}>
        <p className="section-eyebrow">Retail Mind</p>
        <h1>Contact us</h1>
        <p>
          Get help with the customer website, an order, or a shop you found on Retail Mind. Please do not
          include passwords, one-time codes, or payment credentials in any message.
        </p>
      </header>

      <div className={styles.layout}>
        <section className={styles.formSection} aria-labelledby="contact-form-heading">
          <h2 id="contact-form-heading">Send a message</h2>
          {SUPPORT_EMAIL ? (
            <>
              <p className={styles.intro}>
                Choose a subject and write your message. The button below prepares an email in your own
                email app; you review and send it there.
              </p>
              <ContactForm supportEmail={SUPPORT_EMAIL} />
            </>
          ) : (
            <div className={styles.unavailable} role="status">
              <strong>Contact submissions are not available yet.</strong>
              <p>
                A verified support email address has not been configured for this website. For order or
                product questions, open the relevant shop or your orders page and use the contact details
                shown there.
              </p>
              <div className={styles.unavailableLinks}>
                <Link href="/orders">View your orders</Link>
                <Link href="/shops">Browse local shops</Link>
              </div>
            </div>
          )}
        </section>

        <aside className={styles.aside} aria-label="Other ways to get help">
          <h2>Before you write</h2>
          <p>
            Many questions are answered by the shop that fulfils your order. Shop contact details and order
            updates are available in the customer account.
          </p>
          <ul>
            <li><Link href="/orders">Check your order status</Link></li>
            <li><Link href="/shops">Find a shop and its contact details</Link></li>
            <li><Link href="/privacy">Read the privacy information</Link></li>
          </ul>
          <div className={styles.safety}>
            <strong>Keep your account safe</strong>
            <p>
              Retail Mind will not ask for your password or a one-time code by email. If a message asks for
              them, do not reply.
            </p>
          </div>
          {SUPPORT_EMAIL && (
            <p className={styles.directEmail}>
              Prefer your own email app? Write to <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>.
            </p>
          )}
        </aside>
      </div>
    </main>
  );
}
