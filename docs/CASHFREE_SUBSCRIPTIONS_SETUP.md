# Cashfree Subscriptions setup for Retail Mind

## Merchant onboarding

The legally responsible business owner or an adult authorised to operate the business must complete Cashfree merchant onboarding and KYC using accurate business and bank details. Cashfree decides which documents are required for the merchant's business type. Do not use another person's identity or bank details without their authorisation.

Create the merchant account at https://merchant.cashfree.com/merchants/signup. Complete the business profile and requested verification steps. Ask Cashfree to enable **Subscriptions / UPI AutoPay** for the merchant account and confirm that the account supports a refundable ₹1 authorisation amount.

## Sandbox first

1. Sign in to the Cashfree Merchant Dashboard and switch to the Test/Sandbox environment.
2. Open Developers / API Keys and copy the sandbox App ID and Secret Key.
3. In the Retail Mind backend service on Render, add these environment variables:

   - \`CASHFREE_ENV=sandbox\`
   - \`CASHFREE_APP_ID=<sandbox-app-id>\`
   - \`CASHFREE_SECRET_KEY=<sandbox-secret-key>\`
   - \`CASHFREE_WEBHOOK_SECRET=<subscription-webhook-secret>\`
   - \`CASHFREE_API_VERSION=2025-01-01\`
   - \`CASHFREE_AUTHORIZATION_AMOUNT=1\`
   - \`CASHFREE_SUBSCRIPTION_RETURN_URL=<your-https-return-page>\` (optional for native Flutter checkout)

4. Save the Render environment variables and redeploy the backend. Never add Cashfree secrets to Flutter, GitHub source, or any \`NEXT_PUBLIC_*\` variable.

## Configure the subscription webhook

In Cashfree Dashboard, open Developers → Webhooks, select the Subscriptions webhook configuration, and register:

\`https://<your-backend-domain>/api/billing/cashfree/webhook\`

Subscribe to the subscription events:

- \`SUBSCRIPTION_AUTH_STATUS\`
- \`SUBSCRIPTION_STATUS_CHANGED\`
- \`SUBSCRIPTION_PAYMENT_SUCCESS\`
- \`SUBSCRIPTION_PAYMENT_FAILED\`
- \`SUBSCRIPTION_PAYMENT_CANCELLED\`

Use the webhook secret shown by Cashfree as \`CASHFREE_WEBHOOK_SECRET\`. The backend verifies the signature against the raw request body and de-duplicates webhook events.

## Test the complete flow

1. Run the Alembic migration: \`alembic upgrade head\`.
2. Build and install the Flutter Android app with the Cashfree SDK dependency.
3. Sign in as a shop OWNER and open the Retail Mind Plans screen.
4. Select Basic, Pro, or Business and choose Monthly or Yearly.
5. Complete a sandbox subscription authorisation with Cashfree's test payment instructions.
6. Confirm that the signed webhook reaches the backend and that the subscription only becomes ACTIVE after \`SUBSCRIPTION_PAYMENT_SUCCESS\`.
7. Confirm that a failed first payment does not activate the plan; a failed renewal on an already-paid subscription gets the configured three-day grace period.
8. Test duplicate webhook delivery, cancellation, daily AI quota, and the midnight Asia/Kolkata reset.

The ₹1 refundable authorisation is separate from the subscription price. It is not counted as the plan payment and must not activate a paid plan. The current backend sends \`authorization_amount_refund=true\`; do not move to production until Cashfree confirms that this authorisation/refund behaviour is enabled for the merchant's chosen mandate method.

## Go live

Only after sandbox tests pass and Cashfree approves the merchant:

1. Generate the production App ID and Secret Key in the Production environment.
2. Update Render with \`CASHFREE_ENV=production\` and the production credentials.
3. Configure the production subscription webhook endpoint and its secret.
4. Confirm Cashfree has enabled UPI AutoPay / subscriptions and the approved recurring payment methods.
5. Run a controlled live subscription with the business owner's consent and verify the webhook, payment record, renewal date, cancellation and refund behaviour.

Never treat the Flutter checkout callback or a browser redirect as proof of payment. The backend webhook is the source of truth for activation.
