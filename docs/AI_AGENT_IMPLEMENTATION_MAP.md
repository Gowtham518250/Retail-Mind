# Retail Mind AI Agent Automation — Implementation Map

**Base branch:** `production-fix-2026-08-18-playstore`  
**Working branch:** `agentic-retailmind-foundation`  
**Pull request:** [#231](https://github.com/Gowtham518250/Retail-Mind/pull/231)

## Architecture and execution boundaries

The assistant is an orchestration layer over existing Retail Mind services. It does not own a parallel inventory, invoice, customer, order, attendance, or ledger implementation. The authenticated API layer resolves the shop ID; the model cannot provide or override tenant identity.

The current implementation uses:
- LangGraph orchestration with Groq tool calling and a bounded tool loop.
- Explicit Pydantic-validated tool allowlists. There is no arbitrary SQL, shell, filesystem, or unrestricted HTTP tool.
- Owner-authenticated FastAPI endpoints under `/api/agent`.
- PostgreSQL persistence for conversations, pending actions, and metadata-only tool execution audit rows.
- Existing Sarvam Saaras ASR for voice input and Sarvam Bulbul TTS for speech output.
- Existing Retail Mind invoice creation logic for confirmed invoice writes.

## Implemented capabilities

| Capability | Current behavior | Write scope |
| --- | --- | --- |
| Inventory lookup | Active shop catalog, low-stock and product search | Read-only |
| Customer lookup | Active customers in the authenticated shop; phone masked to last four digits in tool output | Read-only |
| Sales analytics | Billed, received and outstanding invoice summary over a bounded date range | Read-only |
| Attendance lookup | Daily shop-scoped attendance summary | Read-only |
| Khata lookup | Invoice-derived pending-payment / receivables view; separate from the legacy `KhataBalance` ledger | Read-only |
| Legacy Khata credit/repayment | Five-minute preview against one phone-number-keyed customer balance; owner confirmation rechecks the balance and writes `KhataBalance`, `KhataHistory` and `UniversalTransaction` atomically with replay protection | Confirmed financial write |
| Online-order lookup | Shop-scoped order status counts and recent order summaries | Read-only |
| Bill preparation | Existing voice-billing parser creates an expiring preview; no invoice or stock mutation | Draft only |
| Bill confirmation | Explicit owner confirmation of a preview hash; uses existing invoice creation service; checks persisted invoice and stock movements | Confirmed financial write |
| Invoice payment | Records one payment against a selected invoice through the existing idempotent Khata payment route; separate five-minute preview and owner confirmation | Confirmed financial write |
| Online-order transition | ACCEPT, DISPATCH and REJECT use the existing order-status service; expected prior status is rechecked at confirmation and the persisted status is verified | Confirmed business write |
| Voice | Sarvam transcription, existing ASR quality guard, shop catalog keyterms | External provider call |
| Speech | Bounded Sarvam Bulbul text-to-speech response | External provider call |

### API surface

- `GET /api/agent/capabilities`
- `POST /api/agent/chat`
- `POST /api/agent/voice`
- `POST /api/agent/speech`
- `GET /api/agent/conversations`
- `GET /api/agent/conversations/{conversation_id}/messages`
- `DELETE /api/agent/conversations/{conversation_id}`
- `GET /api/agent/actions/pending`
- `POST /api/agent/actions/{action_id}/confirm`
- `POST /api/agent/actions/{action_id}/cancel`

Bill, payment and order previews are short-lived, bound to the action, owner/shop, preview and payload by a hash, and require a separate authenticated owner confirmation. Bill confirmation reconciles the deterministic invoice and stock movements; payment confirmation verifies the idempotency-keyed payment row; order confirmation verifies the resulting order status. An order payment entry records the owner-reported receipt; it does not independently verify a bank transfer.

## Deliberately disabled capabilities

These actions remain unavailable to the model:
- Legacy Khata adjustments other than the explicit owner-confirmed CREDIT and REPAYMENT workflow. The repository still contains separate legacy and invoice-derived Khata models, and the assistant does not merge those balances.
- Online-order delivery, cancellation and refund actions. Delivery requires the customer's delivery OTP and payment prerequisites; cancellation/refund require their own verified payment and stock-reversal contracts. Only ACCEPT, DISPATCH and REJECT are implemented through the confirmed workflow.
- Attendance corrections, worker edits and payroll actions. Authorization, approval, correction history and retry/idempotency semantics need to be specified first.
- Any arbitrary database, shell, filesystem or network access.

MCP Streamable HTTP is implemented as an optional adapter over the same allowlisted backend tools. It only mounts when both `RETAIL_MIND_AGENT_ENABLED` and `RETAIL_MIND_MCP_ENABLED` are true, and requires explicit host and origin allowlists. It authenticates the existing Retail Mind OWNER access JWT. MCP protocol POST requests are charged against the same per-shop daily AI quota as the native agent routes. MCP tools can read data or prepare bill, invoice-payment, legacy Khata credit/repayment and order-transition previews; no MCP tool can confirm financial writes or delivery. Confirmation remains in the owner-authenticated app API. This endpoint uses manual Retail Mind bearer JWT authentication; it does not implement an OAuth authorization server or interactive OAuth discovery/login. It remains disabled by default.

## Persistence and migration

Migration `053_agentic_assistant` creates:
- `agent_conversations`
- `agent_messages`
- `agent_pending_actions`
- `agent_tool_executions`

Migration `054_agentic_khata_ledger_idempotency` adds the nullable unique `khata_history.idempotency_key` index used to prevent duplicate legacy-ledger movements. These follow `052_repair_active_product_sku_index` in the Alembic graph. CI validates the migration graph and applies migrations to a clean PostgreSQL database. Production migration execution has not been performed by this PR.

## Security and operational controls

- The shop ID comes from `security.resolve_shop_id(current_user)`, never from the LLM or user-supplied tool arguments.
- Every read query is scoped to the authenticated shop.
- Tool schemas reject unknown fields; call counts, outputs, input sizes and date ranges are bounded.
- Customer phone numbers are masked in tool responses; audit rows store tool metadata rather than raw message or customer payloads.
- Invoice writes require a separate owner confirmation, use the existing invoice path and verify the persisted invoice and stock movements.
- Legacy Khata CREDIT/REPAYMENT previews require owner confirmation, lock and recheck the current balance, and commit the balance, history, universal transaction and completed action in one transaction. A unique history idempotency key prevents duplicate ledger entries.
- Invoice payments require a one-invoice preview, owner confirmation, revalidation of the current outstanding balance and an idempotency key; the preview explicitly warns that it does not verify a bank/cash receipt.
- Order transitions require an owner-confirmed status change, verify the expected prior state at commit time and read the resulting order status back before reporting success.
- The feature flag `RETAIL_MIND_AGENT_ENABLED` defaults to `false` in Render configuration.
- Provider keys are deployment secrets, not source-controlled credentials.
- Provider-backed staging evaluation, load testing, production migration, rollback rehearsal and Flutter integration remain outstanding.

## Validation / rollout status

Latest verified CI on the current PR head:
- Agent backend test job passed.
- Alembic migration graph validation passed.
- Migration upgrade against a clean PostgreSQL CI database passed.
- Production-focused test step was still running at the last status check.
- Staging AI evaluation was skipped because dedicated staging configuration was not present.

Do not enable the feature flag in production until the complete CI run is green, provider credentials and provider terms are reviewed, staging end-to-end tests pass, tenant-isolation and concurrent-confirmation tests pass, and the owner app is integrated and verified. Keep the feature flag off during the initial merge.
