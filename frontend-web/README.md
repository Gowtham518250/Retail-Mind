# Retail Mind customer app

The customer experience is a responsive Next.js storefront that can run in a
browser, install as a PWA, or load inside the Android Capacitor shell.

## Run locally

```bash
npm install
npm run dev
```

The browser API defaults to `https://retail-mind-hpx3.onrender.com`. Set
`NEXT_PUBLIC_API_URL` when the browser should use a different backend. Server
route handlers use `RETAIL_MIND_BACKEND_URL` first and fall back to
`NEXT_PUBLIC_API_URL`.

Set `NEXT_PUBLIC_SITE_URL` to the canonical HTTPS customer website origin before
production deployment. SEO metadata and the sitemap use this trusted setting,
not the incoming request Host header. The current fallback is
`https://retail-mind-web.onrender.com`; confirm that this is the deployed
customer website before launch.

The public `/shops` directory is server-rendered when shop data is available,
then keeps its existing client-side search and filters. Product and shop
catalogue images use the Next.js image optimizer with responsive sizes and
lazy-loading for below-the-fold content. Adding a product animates its image
into the cart; the order-confirmation route animates the parcel along the
backend-reported order status. Both animations respect reduced-motion
preferences.

To enable Google Search Console verification, set
`NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` to the real HTML-tag verification token.
Submit `https://<your-customer-domain>/sitemap.xml` after deployment. No GA4
measurement ID is currently configured; analytics should remain disabled until
the owner supplies an ID and consent requirements are decided.

The public sitemap discovers shops and their products from the existing
backend. It cannot list URLs while that API returns no online-enabled shops.
The current backend returned an empty shop list during frontend launch checks.
The backend has no existing customer contact-submission endpoint, so this
frontend does not show a contact form or report unpersisted messages as sent.
The privacy page is an implementation summary, not a legal-reviewed policy;
the service operator must confirm retention, rights, support contact, and
third-party processing details.

## Web and PWA deployment

Deploy this Next.js app as a server-rendered web app; its same-origin marketplace
and AI routes require the Next.js server. After deployment over HTTPS, customers
can install the PWA from a supported browser.

The repository's root `render.yaml` currently deploys a different, minimal Vite
app from `frontend/`, not this customer app. Deploy `frontend-web/` as a Node
Next.js service (or configure the hosting platform to build this directory)
before expecting these pages, route handlers, sitemap, or metadata on the public
website. The known Render frontend hostname was unavailable during verification.

## Android app

The Capacitor shell loads the deployed web app, so set `CAPACITOR_SERVER_URL` to
the public HTTPS URL before syncing or building Android. Static export is not
configured because the customer app uses server route handlers.

```bash
npx cap sync android
npx cap open android
```

Keep `CAPACITOR_SERVER_URL` pointed at the customer web deployment and
`RETAIL_MIND_BACKEND_URL` pointed at the retail API deployment. Do not use the
backend URL as the Capacitor server URL.
