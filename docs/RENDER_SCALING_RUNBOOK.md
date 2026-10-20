# Retail Mind: Render scaling and load-test runbook

## What this change does

- Runs schema migrations and legacy compatibility DDL through Render's **pre-deploy command**, once per deploy, before new web instances receive traffic.
- Starts the API using a Gunicorn-supervised Uvicorn worker through `production_app.py`. The new ASGI import path does not run schema-changing statements itself.
- Keeps the existing HTTP health check at `/health/ready`.
- Adds k6 GET-based test scripts for gradual constant-rate and virtual-user tests.

It does **not** prove the service can handle 100,000 users. It gives the deployment and test foundation needed to measure capacity safely.

## Architecture

```text
Owner app / Customer app
          |
          | one stable API URL
          v
Render web-service load balancer
          |
     +----+----+
     |    |    |
  API A API B API C      same Render service, same code/version
     |    |    |
     +----+----+
          |
     shared PostgreSQL
          |
     shared Redis/Key Value (when enabled)

Static frontend assets and public images -> a static-site CDN / image CDN
```

Use **multiple instances of one Render web service**, rather than creating unrelated backend services and teaching the apps to choose between their URLs. Render load-balances requests for a scaled web service among its running instances. The customer and owner apps should keep one API base URL.

## Before enabling more than one instance

1. Merge this change only after the pull request checks are reviewed.
2. Use a **paid Render web-service plan**: Render's pre-deploy command is available for paid web services, and Free instances cannot be horizontally scaled.
3. In the Render dashboard, open the existing backend service that serves the production API. Confirm its repository and branch are correct. The service should use these two commands from the Blueprint after syncing the updated `render.yaml`:
   - Pre-deploy: `python predeploy_db.py`
   - Start: `gunicorn --config gunicorn.conf.py production_app:app`
4. Confirm the Health Check Path remains `/health/ready`. Render should wait for healthy new instances before routing traffic to them.
5. Confirm every instance uses the **same** `DATABASE_URL` and `REDIS_URL`. Keep the database and API service in the same Render region. Do not create one database per backend instance.
6. Leave `WEB_CONCURRENCY=1` initially. The app currently starts its attendance reconciliation loop during API startup; the database advisory lock prevents duplicate reconciliation work, but each process still creates a polling thread and its own SQLAlchemy pool. Scale horizontally first. Increase worker processes only after moving scheduled work to a dedicated worker and measuring memory/connection usage.
7. Do not run load tests against production. Create a separate staging API and PostgreSQL database populated with synthetic shops, products, customers, and orders. Use separate staging credentials and secrets.

### Why the pre-deploy step matters

The previous command, `python production_boot.py`, ran database migrations and compatibility DDL whenever a server process started. Several replicas may start together during a scale-out or deployment. The new setup moves those schema changes to the pre-deploy phase and gives the serving processes an ASGI entrypoint that skips the legacy schema-repair block.

Do not manually change the service start command to the new ASGI entrypoint unless the pre-deploy command is enabled too. Otherwise, a missing migration/compatibility step could leave the API running against an outdated schema.

## Scale in stages

1. Start with **2 instances** on staging.
2. Confirm both instances become healthy, normal requests succeed, and no migration runs appear in per-instance startup logs.
3. Run a 1–10 requests/second smoke test, then 25, 50, and 100 requests/second. Hold each stage long enough to collect stable latency, error, CPU, memory, and database-connection measurements.
4. Increase staging load only when the previous stage passes. Keep a rollback path by reducing the instance count or reverting the application deploy. Do not blindly downgrade a database migration.
5. Only after the staged run is clean, test 250, 500, and higher requests/second as the measured infrastructure allows. A 100,000-active-session test needs distributed load generators; do not expect a single laptop or one k6 process to produce that load reliably.
6. Configure autoscaling only after deciding an acceptable minimum/maximum instance count and CPU/memory targets. If autoscaling is not available on the workspace, use manual scaling.

## Database connection budget

SQLAlchemy pool ceilings are **per process**. The current defaults are pool size 5 plus overflow 5, meaning up to 10 pooled connections per worker process under load.

Use this estimate before increasing replicas:

```text
connection ceiling = (DB_POOL_SIZE + DB_MAX_OVERFLOW)
                     × WEB_CONCURRENCY
                     × max API instances
```

Examples with one worker per instance and current pool defaults:
- 2 instances: up to 20 app connections
- 4 instances: up to 40 app connections
- 10 instances: up to 100 app connections

These are configured upper bounds, not observed live connection counts. Reserve database capacity for migrations, background jobs, administration, and other services. If the database connection budget is tight, begin by reducing `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` in staging; do not just scale API instances and hope the database keeps up. `DB_APP_INSTANCE_COUNT` and `DB_CONNECTION_BUDGET` can be set to make existing pool-budget logs more informative.

## Static content and CDN

- Render Static Sites are served through a global CDN. Use a static site for files that can actually be built and served statically.
- The current `frontend-web` customer storefront is deployed separately. This change does not modify its branch or deployment. Verify its Next.js rendering and routes before deciding whether it can be exported as a static site.
- For public product photos, logos, and other uploaded media, use object storage/image hosting plus a CDN when the current backend/database storage is not suited to serving those files at scale.
- Do not cache authenticated API responses, personal/customer data, cart/checkout responses, payment state, or live stock/inventory responses at the edge by default. Dynamic API caching requires explicit rules and correctness tests.

## k6 usage

Install k6 on a dedicated load-test machine or use a managed/distributed k6 runner. These scripts issue GET requests only. They are for safe ramp-up and latency checks, not a complete purchase/workflow test.

### Constant request rate

Start at 10 requests/second against staging:

```bash
k6 run -e API_BASE_URL=https://YOUR-STAGING-API.onrender.com \
  -e READ_PATH=/health/ready -e TARGET_RPS=10 -e DURATION=2m \
  load-tests/k6-constant-rate.js
```

Then change `TARGET_RPS` to 25, 50, and 100 only after each preceding run passes. You can set `READ_PATH` to a safe, read-only API endpoint and optionally pass `API_BEARER_TOKEN` for a staging test user. Avoid paths that write data or trigger paid AI/translation calls.

### Virtual-user ramp

Start with a small number of virtual users:

```bash
k6 run -e API_BASE_URL=https://YOUR-STAGING-API.onrender.com \
  -e READ_PATH=/health/ready -e TARGET_VUS=25 \
  -e RAMP_DURATION=1m -e HOLD_DURATION=2m -e COOLDOWN_DURATION=1m \
  load-tests/k6-ramping-vus.js
```

This repeatedly requests one GET endpoint per virtual user. Large tests (thousands to 100,000 virtual users) should use distributed load generators and coordinated thresholds, with permission from the infrastructure owner.

### Initial acceptance checks

The scripts start with these exploratory thresholds:
- HTTP request failure rate below 1%
- p95 latency below 800 ms
- p99 latency below 1.5 seconds
- more than 99% of expected-status checks pass

Adjust thresholds to real product requirements and endpoint type. A health-check endpoint is useful for initial smoke tests but does not model search, login, checkout, inventory sync, invoice creation, or AI/voice usage. Those workflows need separate staging scenarios using synthetic test accounts and idempotent test data.

During every test, review Render CPU/memory/instance-count and HTTP latency metrics, database active connections and slow-query logs, Redis health, queue depth, 5xx/timeouts, and data correctness. Stop the run if errors or database load grow sharply.

## Deployment checklist

- [ ] Separate staging API + database exists.
- [ ] Staging API uses the updated pre-deploy and Gunicorn start commands.
- [ ] Health check path is `/health/ready`.
- [ ] All instances share the same database and Redis endpoints.
- [ ] `WEB_CONCURRENCY=1` at the start.
- [ ] Database connection ceiling is below the provider's safe connection budget.
- [ ] k6 smoke and 10 RPS test pass.
- [ ] Instance count is raised gradually, with p95/p99, error rates and DB connections reviewed at every stage.
- [ ] Owner and customer apps continue using one stable API base URL.
