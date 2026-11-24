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
| Khata lookup | Invoice-derived pending-payment / receivables view; does not blend the legacy `KhataBalance` ledger | Read-only |
| Online-order lookup | Shop-scoped order status counts and recent order summaries | Read-only |
| Bill preparation | Existing voice-billing parser creates an expiring preview; no invoice or stock mutation | Draft only |
| Bill confirmation | Explicit owner confirmation of a preview hash; uses existing invoice creation service; checks persisted invoice and stock movements | Confirmed financial write |
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

The bill preview is short-lived and bound to the action, owner/shop, preview and payload by a hash. Confirmation is a separate authenticated request. Repeated confirmation reconciles against the deterministic invoice number and persisted invoice/stock records before reporting success.

## Deliberately disabled capabilities

These actions are advertised as not implemented and cannot be invoked by the model:
- Khata credit / repayment writes. Two existing ledger implementations remain; a canonical mutation contract and replay protection are required first.
- Online-order accept/reject/cancel/refund transitions. Each state transition and payment/refund side effect needs a canonical service contract and verified idempotency.
- Attendance corrections, worker edits and payroll actions. Authorization, approval and audit semantics need to be specified first.
- Any arbitrary database, shell, filesystem or network access.

An MCP server and owner Flutter-client integration are not included in this backend PR. They must call the same authenticated API and confirmation flow; they must not create an alternate path to financial writes.

## Persistence and migration

Migration `053_agentic_assistant` creates:
- `agent_conversations`
- `agent_messages`
- `agent_pending_actions`
- `agent_tool_executions`

It follows `052_repair_active_product_sku_index` in the Alembic graph. CI validates the migration graph and applies migrations to a clean PostgreSQL database. Production migration execution has not been performed by this PR.

## Security and operational controls

- The shop ID comes from `security.resolve_shop_id(current_user)`, never from the LLM or user-supplied tool arguments.
- Every read query is scoped to the authenticated shop.
- Tool schemas reject unknown fields; call counts, outputs, input sizes and date ranges are bounded.
- Customer phone numbers are masked in tool responses; audit rows store tool metadata rather than raw message or customer payloads.
- Invoice writes require a separate owner confirmation, use the existing invoice path and verify the persisted invoice and stock movements.
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
