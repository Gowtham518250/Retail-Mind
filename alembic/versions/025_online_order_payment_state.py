"""Persist online-order payment method and notification reconciliation state.

Revision ID: 025_online_order_payment_state
Revises: 024_customer_sync_feed
"""
from alembic import op
import sqlalchemy as sa


revision = "025_online_order_payment_state"
down_revision = "024_customer_sync_feed"
branch_labels = None
depends_on = None


def _columns(bind):
    inspector = sa.inspect(bind)
    if "online_orders" not in inspector.get_table_names():
        raise RuntimeError(
            "Cannot add online-order payment state: online_orders table is missing."
        )
    return {column["name"] for column in inspector.get_columns("online_orders")}


def _indexes(bind):
    return {index["name"] for index in sa.inspect(bind).get_indexes("online_orders")}


def upgrade():
    bind = op.get_bind()
    existing_columns = _columns(bind)

    # The initial online_orders table does not contain idempotency_key, even
    # though this migration later reconciles and indexes it. Ensure the column
    # exists before running the deduplication query.
    required_columns = (
        ("payment_method", sa.String(length=20), False, "COD"),
        ("payment_status", sa.String(length=24), False, "COD_DUE"),
        ("payment_reference", sa.String(length=128), True, None),
        ("payment_detection_key", sa.String(length=128), True, None),
        ("payment_confirmed_at", sa.DateTime(), True, None),
        ("idempotency_key", sa.String(length=128), True, None),
    )
    newly_added_state = set()
    for name, column_type, nullable, default in required_columns:
        if name not in existing_columns:
            kwargs = {"nullable": nullable}
            if default is not None:
                kwargs["server_default"] = default
            op.add_column("online_orders", sa.Column(name, column_type, **kwargs))
            existing_columns.add(name)
            if name in {"payment_method", "payment_status"}:
                newly_added_state.add(name)

    # The old order schema did not persist the payment method/status. Only
    # require review when those fields were introduced by this migration;
    # don't overwrite payment state on a schema where it already existed.
    if newly_added_state:
        bind.execute(sa.text(
            "UPDATE online_orders "
            "SET payment_method = 'UNKNOWN', payment_status = 'REVIEW_REQUIRED'"
        ))

    # Preserve one canonical row for each previously used request key, then
    # enforce idempotency at the database level. Older duplicates remain in
    # order history but no longer claim the retry key.
    bind.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY shop_id, customer_id, idempotency_key
                       ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM online_orders
            WHERE idempotency_key IS NOT NULL
        )
        UPDATE online_orders AS orders
        SET idempotency_key = NULL
        FROM ranked
        WHERE orders.id = ranked.id AND ranked.rn > 1
    """))

    existing_indexes = _indexes(bind)
    if "uq_online_order_request_idempotency" not in existing_indexes:
        op.create_index(
            "uq_online_order_request_idempotency",
            "online_orders",
            ["shop_id", "customer_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
            sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        )
    existing_indexes = _indexes(bind)
    if "uq_online_order_shop_payment_key" not in existing_indexes:
        op.create_index(
            "uq_online_order_shop_payment_key",
            "online_orders",
            ["shop_id", "payment_detection_key"],
            unique=True,
        )


def downgrade():
    bind = op.get_bind()
    existing_indexes = _indexes(bind)
    for name in (
        "uq_online_order_shop_payment_key",
        "uq_online_order_request_idempotency",
    ):
        if name in existing_indexes:
            op.drop_index(name, table_name="online_orders")

    existing_columns = _columns(bind)
    for name in (
        "idempotency_key",
        "payment_confirmed_at",
        "payment_detection_key",
        "payment_reference",
        "payment_status",
        "payment_method",
    ):
        if name in existing_columns:
            op.drop_column("online_orders", name)
