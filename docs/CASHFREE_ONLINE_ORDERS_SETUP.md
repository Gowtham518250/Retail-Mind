# Cashfree PG for Retail Mind online orders

This integration is for **one-time customer orders** in the marketplace. It is separate from Retail Mind's existing Cashfree subscription-billing flow. It uses the same Cashfree App ID / Secret pair but its own explicit feature flag and payment-settlement routes.

## Safety and account ownership

The Cashfree merchant account, KYC, bank details, and production activation must be handled by the legally responsible business owner or an adult authorised to operate that business. Use only accurate business and bank information. Do not use another person's identity, bank account, or credentials without their explicit authorisation. Never paste API keys or webhook secrets into chat, source control, Flutter, or a public frontend variable.

Keep the first deployment in **sandbox**. This code does not switch the account to production or make live charges.

## Backend environment

Add these values to the backend service's secret environment settings (for example, Render). Do not put them in `.env.example` with real values:

```env
CASHFREE_ENV=sandbox
CASHFREE_APP_ID=<sandbox-app-id>
CASHFREE_SECRET_KEY=<sandbox-secret-key>
CASHFREE_API_VERSION=2025-01-01
CASHFREE_PG_ENABLED=true
```

Cashfree PG webhook signature verification uses the Cashfree App Secret by default. The integration accepts the existing `CASHFREE_WEBHOOK_SECRET` fallback and an optional `CASHFREE_PG_WEBHOOK_SECRET` override if the account's webhook configuration uses a distinct signing secret. Keep the override in the backend secret store only.

Optional settings:

```env
CASHFREE_PG_RETURN_URL=https://CUSTOMER_WEB_DOMAIN/payment-return?order_id={order_id}
CASHFREE_PG_NOTIFY_URL=https://BACKEND_API_DOMAIN/api/store/cashfree/webhook
```

The webhook endpoint must also be configured in the Cashfree PG webhook settings for the same environment:

`https://BACKEND_API_DOMAIN/api/store/cashfree/webhook`

Do not point sandbox webhooks at production credentials, or vice versa.

## Database migration

Deploy the backend with the migration:

```bash
alembic upgrade head
```

Revision `045_cashfree_online_order_payments` adds the Cashfree provider order/session/payment references and unique indexes to `online_orders`.

## API flow

The existing customer order endpoint creates the Retail Mind order and reserves stock. The client chooses `payment_method: "UPI"` only when the shop has enabled online payments.

1. Create the Retail Mind order using the existing authenticated customer endpoint:
   `POST /api/store/order`
2. Create/reuse the provider checkout session:
   `POST /api/store/order/{order_id}/cashfree/session`
   The backend calculates the amount from the saved Retail Mind order and returns `cashfree_order_id`, `payment_session_id`, `environment`, and `amount`.
3. Open Cashfree Hosted Checkout with the returned session ID:
   - Web: Cashfree JS SDK `cashfree.checkout({ paymentSessionId, redirectTarget: "_self" })` using mode `sandbox`.
   - Flutter: use Cashfree's Flutter SDK with the returned `order_id` and `payment_session_id`, and environment `CFEnvironment.SANDBOX`.
4. After the SDK callback or customer return, call:
   `GET /api/store/order/{order_id}/cashfree/status`
5. Cashfree sends a signed event to:
   `POST /api/store/cashfree/webhook`

The callback/return URL is only a reason to refresh status. It is never proof of payment. The backend verifies the webhook signature over the exact raw request body, fetches the order and payment from Cashfree's server APIs, checks the order ID, INR currency and exact amount against PostgreSQL, and only then updates `OnlineOrder` and any already-created invoice/payment ledger rows.

## Guest checkout

Guest UPI checkout is intentionally rejected in this first rollout. The payment-status endpoint is customer-authenticated; guest payments need a separately designed, high-entropy checkout capability before they can be safely enabled. Guest orders can continue to use COD.

## Sandbox test plan

Use Cashfree's sandbox payment data shown in its current developer documentation/dashboard. Confirm the following before enabling the payment option for shops:

- Create a small sandbox UPI order and confirm the session contains the server-calculated order amount.
- Complete a successful sandbox payment; confirm the webhook reaches the backend and the order changes from `PENDING` to `PAID`.
- Return to the app after payment and confirm the status endpoint independently reports `PAID`.
- Simulate a failed or abandoned payment; confirm the order is **not** marked paid.
- Deliver the same success webhook more than once; confirm only one payment is posted to the invoice/ledger.
- Verify a wrong signature, mismatched amount, wrong currency, or unknown order cannot mark an order paid.
- Cancel an order before a late successful payment arrives; confirm it is placed in `REFUND_REQUIRED`, not counted as a sale.
- Confirm the existing COD flow and Cashfree subscription billing still work.

The automated tests cover configuration gating, webhook signature calculation, route registration, and guest-checkout protection. A real provider sandbox test still requires the account's sandbox credentials and an accessible deployed webhook endpoint.

## Production transition

Only after sandbox tests pass and the authorised business operator has completed Cashfree's production onboarding:
1. Activate the production PG environment in the Cashfree dashboard.
2. Set `CASHFREE_ENV=production` and the production App ID / Secret in the backend secret store.
3. Configure the production webhook URL and verify its signing secret.
4. Whitelist the customer web domain and set the frontend SDK mode to `production`.
5. Keep `CASHFREE_PG_ENABLED=false` until the production settings and webhook are checked; enable it only after the business owner approves the live launch.

Do not test production with a real customer payment until the business owner has approved the launch and refund/support handling is ready.
