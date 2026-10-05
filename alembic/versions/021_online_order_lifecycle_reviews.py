"""Harden online-order cancellation/return lifecycle.

Revision ID: 021_online_order_lifecycle_reviews
Revises: 020_add_sales_reference_order_id
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


revision = "021_online_order_lifecycle_reviews"
down_revision = "020_add_sales_reference_order_id"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # The original production schema used the native Postgres enum type
    # "order_status", while newer model metadata names it "online_order_status".
    # Detect whichever enum is actually attached to the online_orders column.
    if bind.dialect.name == "postgresql" and "online_orders" in inspector.get_table_names():
        row = bind.execute(sa.text("""
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'online_orders'
              AND column_name = 'order_status'
        """)).first()
        enum_name = row[0] if row else None
        if enum_name:
            for value in ("CANCELLED", "RETURNED"):
                safe_enum = '"' + enum_name.replace('"', '""') + '"'
                bind.execute(sa.text(
                    f"ALTER TYPE {safe_enum} ADD VALUE IF NOT EXISTS '{value}'"
                ))



def downgrade():
    # PostgreSQL enum values are intentionally retained; removing enum values
    # is not safely supported in-place. The sales reference column belongs to
    # revision 020 and is downgraded by that parent revision.
    pass
