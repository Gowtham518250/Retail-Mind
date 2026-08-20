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
    # Production databases can already contain this column even when
    # Alembic's recorded revision is behind. Keep this migration safe to
    # replay/adopt without failing on DuplicateColumn.
    op.execute(
        "ALTER TABLE invoice_line_items "
        "ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2) "
        "NOT NULL DEFAULT 0"
    )
    op.alter_column("invoice_line_items", "discount_amount", server_default=None)


def downgrade():
    op.drop_column("invoice_line_items", "discount_amount")
