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
        # Keep legacy labels readable while adding normalized receipt statuses.
        op.execute("ALTER TYPE purchase_order_status ADD VALUE IF NOT EXISTS 'ORDERED'")
        op.execute("ALTER TYPE purchase_order_status ADD VALUE IF NOT EXISTS 'PENDING'")
        op.execute("ALTER TYPE purchase_order_status ADD VALUE IF NOT EXISTS 'PARTIALLY_RECEIVED'")
        op.execute("ALTER TYPE purchase_order_status ADD VALUE IF NOT EXISTS 'RECEIVED'")

    op.add_column("purchase_orders", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index(
        "uq_purchase_order_shop_idempotency",
        "purchase_orders",
        ["shop_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade():
    op.drop_index("uq_purchase_order_shop_idempotency", table_name="purchase_orders")
    op.drop_column("purchase_orders", "idempotency_key")
    # PostgreSQL enum values are intentionally retained on downgrade to avoid
    # invalidating persisted status rows; they can be removed only by rebuilding the type.
