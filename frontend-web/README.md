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

Set `NEXT_PUBLIC_SITE_URL` to the canonical HTTPS customer website origin in
the deployment environment. SEO metadata and the sitemap use this trusted
setting, not the incoming request Host header. The default is
`https://retail-mind-1.onrender.com`, the currently deployed customer website;
update the setting if the production hostname changes.

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
The deployed backend currently returns an empty shop list, so the sitemap
contains only static public pages until online-enabled shops are available.
The backend has no existing customer contact-submission endpoint, so this
frontend does not show a contact form or report unpersisted messages as sent.
The privacy page is an implementation summary, not a legal-reviewed policy;
the service operator must confirm retention, rights, support contact, and
third-party processing details.

## Web and PWA deployment

Deploy this Next.js app as a server-rendered web app; its same-origin marketplace
and AI routes require the Next.js server. After deployment over HTTPS, customers
can install the PWA from a supported browser.

The customer app is deployed at `https://retail-mind-1.onrender.com`. The
repository's root `render.yaml` still describes a different, minimal Vite app
from `frontend/`; it does not configure this Next.js service.
`/shops` loads discovery results through the same-origin `/api/marketplace/search`
route so browser requests do not depend on backend CORS for that page. Other
browser-to-backend features still require the API service's `ALLOWED_ORIGINS`
setting to include `https://retail-mind-1.onrender.com`.

## Android app

The Capacitor Android shell loads the deployed customer app at
`https://retail-mind-1.onrender.com` by default. It uses the live HTTPS site,
including its server-rendered pages and API routes, so an internet connection is
required. Set `CAPACITOR_SERVER_URL` only when building against a different
customer deployment; do not point it at the retail API.

```bash
npm run build
npx cap sync android
cd android
gradlew.bat assembleDebug
```

Install the debug package from
`android/app/build/outputs/apk/debug/app-debug.apk`. For Google Play, create a
signed Android App Bundle (`bundleRelease`) in Android Studio using a protected
release keystore; never commit the keystore or signing credentials. Android
builds require a configured JDK and Android SDK.
