# Retail Mind Agent Automation — Implementation Map

**Base branch:** `production-fix-2026-08-18-playstore`  
**Working branch:** `agentic-retailmind-foundation`

## Design rule

The assistant is an orchestration layer, not a second ERP. It must call existing
Retail Mind business services/routes and preserve their validation, stock
movement, ledger, transaction, and audit behavior. The LLM must never write SQL,
choose a shop ID, invent prices/quantities, or claim a write succeeded without
reading the canonical persisted result.

## Existing backend foundations verified in this branch

- `app.py` registers inventory, inventory sync/reconciliation, invoices,
  customers, attendance, Khata, online store, retail intelligence, realtime,
  durable sync, and health routers.
- `security.py` provides `owner_only`, `get_current_user_dict`, and
  `resolve_shop_id`. Owner identity must be derived from the access token.
- `inventory.py` owns inventory and voice-billing routes. Voice parsing is a
  draft/prefill operation; it must not create an invoice or deduct stock.
- `invoices_billing.py` owns invoice creation and payment handling. Reuse its
  canonical creation path; do not implement invoice or stock writes separately.
- `customers.py` owns customer CRUD and search.
- `khata_ledger.py` and `khata_router.py` contain legacy and newer ledger
  routes. Select one canonical write path only after reviewing both contracts.
- `online_store.py` owns customer/store and owner-order workflows.
- `attendance.py` owns attendance operations.
- `retail_intelligence.py` owns expenses, workers, bank reconciliation,
  enterprise summaries, and stock analysis.

## Capability-to-module map

| Agent capability | Existing source of truth | Risk | Gate before enabling |
| --- | --- | --- | --- |
| Inventory lookup | `inventory.py` | Read | Owner auth; shop-scoped query; no cross-shop product IDs |
| Customer lookup | `customers.py` | Read / personal data | Owner auth; shop scope; return minimum fields; mask phone in logs |
| Prepare bill | `inventory.py` voice parser + invoice schemas | Draft | Ground every product in shop catalog; quantity/price validation; no write |
| Create invoice | `invoices_billing.py` | Financial write | Explicit owner confirmation; existing invoice path; idempotency key; verify invoice and stock movement |
| Record Khata credit/repayment | `khata_ledger.py` / `khata_router.py` | Financial write | Choose canonical ledger; explicit confirmation; replay protection; verify ledger entry |
| Manage online orders | `online_store.py` | Business write | Owner auth and entitlement checks; confirmation for accept/cancel/refund; verify order state |
| Attendance lookup/action | `attendance.py` | Employee data / write | Owner or permitted role; shop scope; confirmation for corrections |
| Analytics | `retail_intelligence.py`, invoice and inventory services | Read | Parameterized fixed queries only; shop scope; bounded date range |

## Delivery sequence

1. **Foundation (this commit):** owner-only capability discovery, central registry,
   implementation map. No business tool is executable yet.
2. **Read-only tools:** inventory lookup, customer lookup, attendance lookup,
   and bounded analytics. Add unit and cross-shop isolation tests.
3. **Billing vertical slice:** parse voice/text into a draft, resolve catalog
   products, ask for missing details, show a human-readable bill, require a
   separate confirmation call, create through the canonical invoice service,
   and verify invoice + stock movement.
4. **Khata and orders:** select canonical route/service contracts, add
   idempotency and explicit confirmations, then integration tests.
5. **Voice:** connect existing Sarvam ASR; add TTS only after provider,
   language, timeout, and fallback decisions are verified.
6. **LangGraph/MCP:** introduce orchestration after deterministic tools are
   tested. MCP should expose the same allowlisted tools, not create a second
   business-logic implementation.

## Non-negotiable safety controls

- Derive `shop_id` from authenticated owner context; ignore shop IDs supplied
  by model output or untrusted request text.
- No arbitrary SQL, Python execution, shell access, or unrestricted HTTP tool.
- Separate read, draft, and write capabilities.
- Financial and destructive actions require explicit confirmation bound to
  the exact preview (amount, customer, items, quantities, and operation).
- Use idempotency keys for retries; never infer success from an LLM response.
- Audit tool name, authenticated user/shop, confirmation, outcome, and
  correlation ID. Do not log OTPs, tokens, full payment details, or raw voice
  recordings/transcripts unnecessarily.
- Enforce timeouts, bounded inputs/results, rate limits, and per-user limits.
- On ambiguity, ask the owner; never invent missing product, price, quantity,
  customer, payment, or order data.

## Current status

The first foundation commit adds a central capability registry and an
owner-authenticated discovery endpoint. All capabilities are intentionally
`enabled: false`; no agent business action is exposed until its contract and
tests are implemented. This is deliberate fail-closed behavior, not a claim
that the whole automation system is complete.
