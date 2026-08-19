"""Persist invoice line discount metadata.

Revision ID: 008_add_invoice_line_discount_amount
Revises: 007_merge_migration_heads
"""
from alembic import op
import sqlalchemy as sa

revision = "008_add_invoice_line_discount_amount"
down_revision = "007_merge_migration_heads"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "invoice_line_items",
        sa.Column("discount_amount", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.alter_column("invoice_line_items", "discount_amount", server_default=None)

def downgrade():
    op.drop_column("invoice_line_items", "discount_amount")
