"""Run schema migrations and legacy compatibility DDL once before a Render deploy.

Configure this script as the web service's Render pre-deploy command. Do not use
it as the web process entrypoint: Render runs pre-deploy once per deploy, before
new instances receive traffic, while all web instances then start production_app:app.
"""
import os


def main() -> None:
    # Refuse to run against a local fallback database by accident. Render injects
    # DATABASE_URL for the configured PostgreSQL database.
    if not os.environ.get("DATABASE_URL", "").strip():
        raise RuntimeError(
            "DATABASE_URL is required for the pre-deploy database bootstrap; "
            "refusing to use fallback database settings."
        )

    from production_boot import (
        _ensure_online_delivery_payment_trigger,
        _ensure_online_order_status_enum,
        _ensure_sales_reference_order_id,
        _ensure_shift_table,
        _ensure_workers_table_schema,
        _run_database_migrations,
    )

    print("[PREDEPLOY] Starting database migration and compatibility checks.", flush=True)
    _run_database_migrations()
    _ensure_online_order_status_enum()
    _ensure_sales_reference_order_id()
    _ensure_online_delivery_payment_trigger()
    _ensure_workers_table_schema()
    _ensure_shift_table()
    print("[PREDEPLOY] Database bootstrap completed.", flush=True)


if __name__ == "__main__":
    main()
