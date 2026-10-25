# Verified payment settlement

## Safety model

An Android SMS or app notification is a detection signal, not proof that funds reached the shop. The client may still announce a *possible* transfer and ask the shopkeeper to check their bank, but it must not use that text alone for automatic settlement.

The backend now supports a short-lived, invoice-bound payment intent and a signed provider callback. Settlement is accepted only when the callback signature is valid and the provider, successful status, exact amount in paise, invoice outstanding balance, and shop UPI destination all match the server-created intent. Replays of the same provider transaction are idempotent; a second transaction cannot settle an already-paid intent.

## Configuration

Set these on the backend host (not in Flutter/web client code):

- `PAYMENT_VERIFICATION_WEBHOOK_SECRET`: a random secret of at least 32 characters. Configure the same secret in the trusted bank/PSP adapter that signs callbacks.
- `PAYMENT_VERIFICATION_PROVIDER`: provider identifier, default `bank_psp`; the callback's provider must match it.
- `PAYMENT_INTENT_TTL_MINUTES`: intent lifetime in minutes, bounded server-side to 5–60; default 15.

Leave the webhook secret unset until the trusted provider adapter is configured. Intent creation is intentionally disabled if the secret is missing or too short.

## API contract

### 1. Create an intent

Authenticated shop owner/worker:

`POST /api/invoices/payment-intents`

Body:

```json
{"invoice_id": 123}
```

The server finds the invoice scoped to the logged-in shop and creates an intent for the *current outstanding balance*, not a caller-supplied amount. The response contains `intent_reference`, `amount_paise`, `currency`, `destination_vpa`, provider, status and expiration. The client can show the exact configured UPI destination and amount, and include the intent reference in the payment note where supported.

### 2. Provider callback

`POST /api/invoices/payment-provider/webhook`

Header:

`X-Payment-Signature: <lowercase HMAC-SHA256 hex>`

The signature is HMAC-SHA256 over the exact raw request bytes, using `PAYMENT_VERIFICATION_WEBHOOK_SECRET`. A `sha256=` prefix is also accepted.

The trusted provider adapter must send a JSON body matching this contract:

```json
{
  "provider": "bank_psp",
  "event_id": "event-unique-id",
  "intent_reference": "RMP-server-generated-reference",
  "provider_transaction_id": "bank-or-psp-transaction-id",
  "amount_paise": 12345,
  "currency": "INR",
  "destination_vpa": "shop@bank",
  "status": "SUCCESS"
}
```

Only `SUCCESS`, `CAPTURED`, `PAID`, or `COMPLETED` states are eligible for settlement. Failure/pending states are acknowledged without changing the invoice. Amount or destination mismatch, stale intent, changed invoice balance, wrong provider, invalid signature, and duplicate transaction reuse are rejected. The callback must report the *actual beneficiary VPA from trusted provider/bank data*; echoing the VPA from client input or order notes is not destination verification.

## Integration boundary

This adds the backend contract and safety checks; it does not create a bank/PSP merchant account or install/configure the provider's webhook in its dashboard. A provider adapter must deliver the normalized signed event above and must source the beneficiary VPA from its trusted transaction record. If a chosen gateway cannot attest the actual destination VPA, do not map its payer VPA or client-supplied metadata into `destination_vpa`; those fields are not proof of the beneficiary account. Until a suitable adapter and secret are configured, the API fails closed and does not auto-settle from notifications.
