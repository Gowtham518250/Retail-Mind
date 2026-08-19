"""Repair invoice line discount column for existing production databases.

Revision ID: 010_repair_invoice_line_discount_amount
Revises: 009_merge_invoice_and_attendance_heads
"""
from alembic import op

revision = "010_repair_invoice_line_discount_amount"
down_revision = "009_merge_invoice_and_attendance_heads"
branch_labels = None
depends_on = None


def upgrade():
    # Some databases have already recorded revision 009 while the physical
    # column is missing. Repair the schema without touching existing data.
    op.execute(
        "ALTER TABLE invoice_line_items "
        "ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2) "
        "NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE invoice_line_items "
        "ALTER COLUMN discount_amount DROP DEFAULT"
    )


def downgrade():
    # Only remove the column when rolling back this repair migration.
    op.execute(
        "ALTER TABLE invoice_line_items DROP COLUMN IF EXISTS discount_amount"
    )
