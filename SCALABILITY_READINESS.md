# Retail Mind: Scalability Readiness Plan

## Goal and non-goal

The target is **100,000 simultaneous active users**, not merely 100,000 registered accounts. This is an engineering target, not a capacity claim. Capacity must be demonstrated with repeatable tests against production-like infrastructure.

Illustrative request rates:
- One request per active user every 30 seconds: about 3,333 requests/second.
- One request per active user every 10 seconds: about 10,000 requests/second.
- UI screens can issue multiple API calls; AI/voice operations have a different cost profile. Model actual user journeys before capacity planning.

## Current backend changes in this branch

- SQLAlchemy pool size and overflow are environment-driven and conservative by default.
- Pool connection ceilings are calculated across configured workers and instances; an optional DB_CONNECTION_BUDGET produces a warning if the configured ceiling is larger.
- Dedicated /health/live and /health/ready endpoints separate process liveness from database readiness. Redis is not a readiness dependency because the current backend intentionally has an in-memory fallback.
- A configurable k6 HTTP load-test script is supplied for controlled staging tests.
- See this checklist before a high-traffic release.

## Database connection budget

Pool limits apply **per process**, not per service. Estimate the maximum app-side connections as:

`instances × workers_per_instance × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`

For example, 4 instances × 2 workers × (5 + 5) = 80 possible connections. This is arithmetic only; it does not imply a specific PostgreSQL provider will allow 80 connections.

Configure these variables in the service's environment as appropriate for the database plan:
- `DB_POOL_SIZE` (default 5; supported 1–100)
- `DB_MAX_OVERFLOW` (default 5; supported 0–100)
- `DB_POOL_TIMEOUT_SECONDS` (default 15; supported 1–300)
- `DB_POOL_RECYCLE_SECONDS` (default 1800; supported 60–86400)
- `DB_CONNECTION_BUDGET` (optional provider-confirmed budget; emits a warning if exceeded)
- `WEB_CONCURRENCY` (worker count used for the estimate; the value must match actual server process configuration)
- `DB_APP_INSTANCE_COUNT` (optional estimate override; defaults to 1)

Do not raise pool size to increase user capacity without also checking the database provider's connection ceiling, query latency and pool wait times. A pooler can reduce connection churn, but it does not make expensive queries cheaper.

## Deployment health checks

- `GET /health/live`: process-only liveness; should not call PostgreSQL or Redis.
- `GET /health/ready`: checks that PostgreSQL can execute `SELECT 1`; returns 503 if the database is unavailable.
- Existing `GET /health` is retained for compatibility.

When configuring a platform readiness/health-check path, prefer `/health/ready`. Use `/health/live` only for process liveness. A live/ready response is not a substitute for synthetic tests of authentication, inventory or order flows.

## Required architecture before 100,000 concurrent users

1. Keep API replicas stateless. Store durable data in PostgreSQL/object storage and shared, expiring coordination state in Redis or another managed shared service.
2. Repair and verify Redis connectivity; the in-memory fallback is per process and is not a distributed rate limiter. The cache can safely bypass Redis and retry, but cache hits and shared rate limits require a healthy common Redis endpoint. Use atomic Redis operations and test failover.
3. Separate expensive AI, speech and document-indexing work into bounded worker pools and queues. Apply timeouts, quotas, backpressure and safe retries.
4. Budget connections across every process and replica. Review slow queries, indexes, transaction lengths and N+1 query patterns; use read replicas only for appropriate read workloads.
5. Keep order/inventory/payment changes transactional and idempotent. Never use a cache as the source of truth for stock, invoices or payments.
6. Use object storage and a CDN for product images and public assets; avoid large image payloads and shared state on local disks.
7. Add monitoring for request rate, latency percentiles, errors, pool checkout waits, DB connections, Redis errors, queue depth, worker duration, memory and CPU.
8. Validate backup restoration, dependency outages, rate limiting, tenant isolation, order idempotency and rollback procedures.
9. Scale from measurements; 100,000 concurrent users can translate into thousands of requests per second, so instance count and budget cannot be responsibly guessed before testing.

## Controlled k6 tests

Install k6 on a test machine/CI runner and use a **staging** URL. Start small and increase gradually:

```bash
BASE_URL=https://your-staging-api.example \
VUS=10 DURATION=1m \
k6 run tests/load/k6_api_load.js
```

For a representative, safe read-only endpoint:

```bash
BASE_URL=https://your-staging-api.example \
TARGET_PATH=/your/read-only-endpoint \
VUS=100 DURATION=5m \
k6 run tests/load/k6_api_load.js
```

For a protected read-only endpoint, supply a test account's short-lived token via `AUTH_TOKEN` in the shell environment. Never commit credentials or run write-heavy, 100,000-user tests against production without an approved test window and a rollback plan. The default target is only `/health/live`, which validates basic HTTP serving but does not represent business API/database capacity.

Recommended stages: 10 → 50 → 100 → 250 → 500 → 1,000 → 5,000 and higher only when the previous stage meets agreed p95-latency and error-rate objectives. A full 100,000-user run requires distributed load generators, representative journeys, monitoring and an environment sized like the intended production deployment.

## Definition of done

Do not claim 100,000-user readiness until:
- tests run at agreed concurrency with a documented request mix;
- p95/p99 latency and error budgets pass;
- no database connection exhaustion, Redis failure cascade or unbounded queue growth occurs;
- no duplicate orders/invoices or cross-shop data exposure occurs under retries/concurrency;
- recovery tests and a rollback procedure have passed;
- results and cost estimates are recorded for the exact deployment revision.
