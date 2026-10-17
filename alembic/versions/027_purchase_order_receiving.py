"""Add purchase-order idempotency and receipt lifecycle values.

Revision ID: 027_purchase_order_receiving
Revises: 026_product_image_url
"""
from alembic import op
import sqlalchemy as sa

revision = "027_purchase_order_receiving"
down_revision = "026_product_image_url"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # The initial schema calls this enum 'po_status', while some adopted
        # production schemas call it 'purchase_order_status'. Resolve the type
        # actually used by purchase_orders.status rather than assuming one name.
        enum_name = bind.execute(sa.text("""
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'purchase_orders'
              AND column_name = 'status'
        """)).scalar()
        allowed_enum_names = {"po_status", "purchase_order_status"}
        if enum_name in allowed_enum_names:
            for label in ("ORDERED", "PENDING", "PARTIALLY_RECEIVED", "RECEIVED"):
                op.execute(
                    sa.text(
                        f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{label}'"
                    )
                )

    bind = op.get_bind()
    existing_columns = {
        column["name"] for column in sa.inspect(bind).get_columns("purchase_orders")
    }
    if "idempotency_key" not in existing_columns:
        op.add_column(
            "purchase_orders",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )

    existing_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("purchase_orders")
    }
    if "uq_purchase_order_shop_idempotency" not in existing_indexes:
        op.create_index(
            "uq_purchase_order_shop_idempotency",
            "purchase_orders",
            ["shop_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
            sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        )


def downgrade():
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("purchase_orders")}
    if "uq_purchase_order_shop_idempotency" in indexes:
        op.drop_index("uq_purchase_order_shop_idempotency", table_name="purchase_orders")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("purchase_orders")}
    if "idempotency_key" in columns:
        op.drop_column("purchase_orders", "idempotency_key")
    # PostgreSQL enum values are intentionally retained on downgrade to avoid
    # invalidating persisted status rows.
