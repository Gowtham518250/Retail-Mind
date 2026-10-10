"""Add online-order reference to legacy sales rows.

Revision ID: 020_add_sales_reference_order_id
Revises: 019_retail_growth_suite
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa


revision = "020_add_sales_reference_order_id"
down_revision = "019_retail_growth_suite"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sales" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("sales")}
    if "reference_order_id" not in columns:
        op.add_column("sales", sa.Column("reference_order_id", sa.Integer(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("sales")}
    if "ix_sales_reference_order_id" not in indexes:
        op.create_index("ix_sales_reference_order_id", "sales", ["reference_order_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "sales" not in inspector.get_table_names():
        return

    indexes = {index["name"] for index in inspector.get_indexes("sales")}
    if "ix_sales_reference_order_id" in indexes:
        op.drop_index("ix_sales_reference_order_id", table_name="sales")

    columns = {column["name"] for column in inspector.get_columns("sales")}
    if "reference_order_id" in columns:
        op.drop_column("sales", "reference_order_id")
