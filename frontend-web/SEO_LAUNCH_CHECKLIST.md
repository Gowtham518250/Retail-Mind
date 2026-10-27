# Google Search setup for Retail Mind

## Current public website

The live website checked during this work is:

- Website: https://retail-mind-1.onrender.com/
- Sitemap: https://retail-mind-1.onrender.com/sitemap.xml
- Robots: https://retail-mind-1.onrender.com/robots.txt

The older address https://retail-mind-web.onrender.com/ returned a Render “Service Suspended” page during the same check. Register the active website in Search Console, not the suspended address, unless you reactivate that service and intentionally use it.

## Code preparation

- The homepage has a canonical URL and descriptive page metadata.
- The shops directory has its own title and description.
- Public shop and product pages generate their own metadata and structured data.
- `/robots.txt` permits crawling of public pages and excludes account, order, API and checkout routes.
- `/sitemap.xml` lists the homepage, shops directory, public shop pages and product pages.
- The homepage no longer auto-redirects first-time visitors to the splash screen. The splash route is explicitly marked `noindex`.
- The root layout already supports Google’s HTML-tag verification through `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION`.
- The canonical host is configurable with `NEXT_PUBLIC_SITE_URL`. Keep it set to the exact production website origin.

## Required owner steps in Google Search Console

1. Open https://search.google.com/search-console/ and sign in to the Google account that should own the property.
2. Add a URL-prefix property for `https://retail-mind-1.onrender.com/`.
3. Choose HTML-tag verification and copy the unique verification token from Google. Do not copy an example token from this repository.
4. In the frontend service's deployment environment, set `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION` to that token. Confirm `NEXT_PUBLIC_SITE_URL=https://retail-mind-1.onrender.com`.
5. Redeploy the frontend, return to Search Console and click Verify.
6. In Search Console → Sitemaps, submit `sitemap.xml`.
7. Use URL Inspection for the homepage and `https://retail-mind-1.onrender.com/shops`. Run the live test, then request indexing if Google reports the page is indexable.
8. Later, review the Pages/Indexing report for crawl errors, canonical mismatches, and “Crawled - currently not indexed” URLs.

## Important

Sitemap submission and requesting indexing are discovery signals, not a guarantee of inclusion or ranking. Google decides which pages to index and how to rank them. It may take days or longer for changes to appear. Helpful, unique page content, reliable public access, internal links and a stable canonical domain also matter.

Do not put private account pages, customer-specific information, orders, checkout URLs, or user tokens in the sitemap.
