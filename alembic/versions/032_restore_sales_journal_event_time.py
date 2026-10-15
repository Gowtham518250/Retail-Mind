"""Restore SALE journal timestamps from canonical invoice event times.

Revision ID: 032_restore_sales_journal_event_time
Revises: 031_stock_movement_idempotency

Legacy sales journal rows were created at midnight using invoice_date. Where a
matching invoice has a meaningful created_at timestamp, this data migration
copies that canonical event time to the SALE income journal row. Rows with no
matching invoice or an invoice timestamp at midnight are left unchanged.
"""
from alembic import op
import sqlalchemy as sa

revision = "032_restore_sales_journal_event_time"
down_revision = "031_stock_movement_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("""
            UPDATE universal_transactions AS tx
            SET tx_date = invoice.created_at
            FROM invoices AS invoice
            WHERE tx.shop_id = invoice.user_id
              AND tx.reference_id = invoice.invoice_number
              AND tx.category = 'SALE'
              AND tx.tx_type = 'INCOME'
              AND tx.tx_date IS NOT NULL
              AND CAST(tx.tx_date AS time) = TIME '00:00:00'
              AND invoice.created_at IS NOT NULL
              AND CAST(invoice.created_at AS time) <> TIME '00:00:00'
        """))
    elif bind.dialect.name == "sqlite":
        op.execute(sa.text("""
            UPDATE universal_transactions
            SET tx_date = (
                SELECT invoice.created_at
                FROM invoices AS invoice
                WHERE invoice.user_id = universal_transactions.shop_id
                  AND invoice.invoice_number = universal_transactions.reference_id
                  AND invoice.created_at IS NOT NULL
                  AND time(invoice.created_at) <> '00:00:00'
                ORDER BY invoice.id DESC
                LIMIT 1
            )
            WHERE universal_transactions.category = 'SALE'
              AND universal_transactions.tx_type = 'INCOME'
              AND universal_transactions.tx_date IS NOT NULL
              AND time(universal_transactions.tx_date) = '00:00:00'
              AND EXISTS (
                  SELECT 1
                  FROM invoices AS invoice
                  WHERE invoice.user_id = universal_transactions.shop_id
                    AND invoice.invoice_number = universal_transactions.reference_id
                    AND invoice.created_at IS NOT NULL
                    AND time(invoice.created_at) <> '00:00:00'
              )
        """))
    else:
        raise RuntimeError(
            "032_restore_sales_journal_event_time supports PostgreSQL and SQLite only"
        )


def downgrade():
    # This is a one-way correction from a lossy midnight timestamp to a
    # canonical invoice event timestamp. Resetting rows to midnight would
    # reintroduce the data defect, so the corrected data intentionally remains.
    pass
