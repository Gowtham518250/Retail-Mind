"""Harden online-order cancellation/return lifecycle.

Revision ID: 020_online_order_lifecycle_reviews
Revises: 019_retail_growth_suite
Create Date: 2026-10-03
"""

from alembic import op
import sqlalchemy as sa


revision = "020_online_order_lifecycle_reviews"
down_revision = "019_retail_growth_suite"
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

    tables = inspector.get_table_names()
    if "sales" in tables:
        columns = {c["name"] for c in inspector.get_columns("sales")}
        if "reference_order_id" not in columns:
            op.add_column(
                "sales",
                sa.Column("reference_order_id", sa.Integer(), nullable=True),
            )
            op.create_index(
                "ix_sales_reference_order_id",
                "sales",
                ["reference_order_id"],
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "sales" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("sales")}
        if "reference_order_id" in columns:
            op.drop_index("ix_sales_reference_order_id", table_name="sales")
            op.drop_column("sales", "reference_order_id")

    # Postgres does not safely support removing enum values in-place.
