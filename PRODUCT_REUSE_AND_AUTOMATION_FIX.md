# Product recreation and backend poster automation

## Product recreation
- Create idempotency now returns an existing product only while it is active.
- If the idempotency record points to an archived product, that stale record is removed and a new product can be created.
- Bulk import only treats active products as duplicates; it no longer silently reactivates archived products.
- Bulk-created products enqueue the same opt-in new-product marketing trigger as individually created products.
- Migration 052 removes legacy all-row shop/SKU uniqueness and guarantees the active-only partial unique index.

## Server-generated posters
- The existing scheduled worker continues to create private campaign drafts from queued triggers.
- A shop-scoped GET endpoint serves the saved SVG as `image/svg+xml`, so clients do not need to render or edit the artwork.
- The existing campaign list response continues to include `poster_svg`; a direct poster endpoint is also available.
- Drafts remain pending owner approval; no automatic social publishing is introduced.

## Deployment
Render must deploy the branch after merge. Confirm Alembic applies revision
`052_repair_active_product_sku_index`. Confirm
`GROWTH_MARKETING_AUTOMATION_WORKER_ENABLED` is unset or set to `1`.
The worker runs on a 60-second loop and uses the PostgreSQL advisory lock so
only one replica processes the shared queue at a time.
