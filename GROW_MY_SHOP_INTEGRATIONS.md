# Grow My Shop — social and creative integration plan

## Current implementation

The current Growth Agent provides:

- Local poster rendering and native device sharing.
- Server-assisted, shop-scoped copy generation when Groq is configured.
- Deterministic local copy fallback when the backend or AI service is unavailable.
- Owner-scoped draft persistence through the campaign endpoints.
- Drafts remain `DRAFT` and require owner review. Nothing is auto-published or paid for.

The backend validates the authenticated shop and re-checks selected products against that shop's inventory before generating or saving a draft. The marketing-copy guard rejects categories that should not be promoted through this feature.

## Instagram and Facebook Pages

Use Meta's official Graph APIs for organic publishing after the app and each shop owner have completed authorization.

For the Facebook Login configuration, the Instagram account must be a Professional account linked to a Facebook Page. Consumer Instagram accounts are not supported by this API configuration. The current Meta Instagram collection documents the relevant content-publishing permissions and account limitations:

- https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api
- https://www.postman.com/meta/facebook/documentation/r56bjfd/facebook-api

Before production publishing is enabled:

1. Create and configure a Meta Business app, callback URL, privacy policy and data-deletion path.
2. Complete the required App Review / Advanced Access for the requested permissions.
3. Let each shop owner authorize only the Page and Professional Instagram account they administer.
4. Store access tokens only on the backend, encrypted at rest, scoped to the authenticated shop, and never return them to Flutter.
5. Add per-shop publishing queues, idempotency keys, retry limits, audit history and an explicit owner approval step before each post is published.

The first publishing release should cover approved organic Page and Instagram posts. Paid-ad account creation, campaign budgets and billing are not part of this implementation.

## WhatsApp Business

Treat WhatsApp as a separate, opt-in business-messaging integration, not as a Status publisher.

Meta's official WhatsApp Business Platform docs describe Cloud API messaging, Business Account onboarding and Embedded Signup. Some outbound messages require approved templates; recipients must have opted in and opt-outs must be respected.

- https://www.postman.com/meta/whatsapp-business-platform/overview
- https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api
- https://www.postman.com/meta/whatsapp-business-platform/documentation/du6gzjv/embedded-signup

Production prerequisites include a Meta Business portfolio, a WhatsApp Business Account, a registered business phone number, the appropriate app permissions and webhook verification. Customer consent and opt-out state must be recorded before a marketing message can be queued.

## Adobe Express

Adobe Express Premium storage is not an API credential and does not grant Retail Mind permission to publish into social networks.

Two Adobe developer paths are relevant:

- **Embed SDK:** interactive editing inside the Retail Mind web experience. Adobe currently requires business approval for new integrations.
- **Express API:** headless programmatic asset generation and export. Adobe's published FAQ says the current API beta is for testing/evaluation only and must not be used for commercial purposes or deployed to production.

References:

- https://developer.adobe.com/express/embed-sdk/docs/guides/
- https://developer.adobe.com/express/embed-sdk/docs/guides/quickstart/
- https://developer.adobe.com/firefly-services/docs/express-api/getting-started/support/FAQ/

Until the relevant Adobe production approval/terms are available, Retail Mind should keep its native poster generator and manual export/share workflow. Do not send customer data or production campaign content to an unapproved beta endpoint.

## Required server configuration for a future Meta connector

Keep these values in the backend secret manager, never in the Flutter app:

- `META_APP_ID`
- `META_APP_SECRET`
- `META_OAUTH_REDIRECT_URI`
- `META_GRAPH_API_VERSION`
- `META_TOKEN_ENCRYPTION_KEY`

The integration is not considered connected just because these values exist. A shop connection is only active after an owner completes OAuth, the backend validates the returned account/Page relationship, required permissions are granted, and the encrypted token record is saved under that shop.

WhatsApp Embedded Signup and Adobe Embed SDK approval have separate onboarding and verification requirements. They should not reuse a Facebook Page token as though it were a WhatsApp credential or an Adobe credential.
