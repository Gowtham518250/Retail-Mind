"""Force-repair the invoice line discount column in production.

Revision ID: 011_force_invoice_line_discount_schema
Revises: 010_repair_invoice_line_discount_amount
"""

from alembic import op

revision = "011_force_invoice_line_discount_schema"
down_revision = "010_repair_invoice_line_discount_amount"
branch_labels = None
depends_on = None


def upgrade():
    # The production database can have Alembic revision state ahead of the
    # physical schema. Always make the column available before invoice queries.
    op.execute(
        "ALTER TABLE invoice_line_items "
        "ADD COLUMN IF NOT EXISTS discount_amount NUMERIC(10, 2) "
        "NOT NULL DEFAULT 0"
    )


def downgrade():
    # Keep rollback safe for databases where the column may already have
    # existed before this repair migration.
    op.execute(
        "ALTER TABLE invoice_line_items "
        "DROP COLUMN IF EXISTS discount_amount"
    )
