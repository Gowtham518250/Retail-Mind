"""Repair zero-paid invoices explicitly marked as completed regular cash sales.

Revision ID: 030_regular_cash_paid_state
Revises: 029_expense_idempotency

Only OFFLINE_SYNC cash invoices with the explicit Regular Sale marker are
reconciled. Borrow invoices, non-cash payments, partial receipts, drafts and
cancelled documents are left unchanged. No payment-ledger entries are invented.
"""
from alembic import op

revision = "030_regular_cash_paid_state"
down_revision = ("029_expense_idempotency", "e7a9054db41d")
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE invoices
        SET paid_amount = total_amount,
            payment_method = 'CASH',
            payment_status = 'PAID',
            status = 'PAID',
            updated_at = CURRENT_TIMESTAMP
        WHERE COALESCE(paid_amount, 0) = 0
          AND COALESCE(total_amount, 0) > 0
          AND source = 'OFFLINE_SYNC'
          AND (
              UPPER(COALESCE(payment_method, '')) IN ('CASH', 'COD', 'CASH ON DELIVERY')
              OR LOWER(COALESCE(notes, '')) LIKE '%payment via cash%'
          )
          AND (payment_status IS NULL OR payment_status IN ('UNPAID', 'OVERDUE'))
          AND (status IS NULL OR status NOT IN ('CANCELLED', 'DRAFT'))
          AND LOWER(COALESCE(notes, '')) LIKE '%regular sale%'
          AND LOWER(COALESCE(notes, '')) NOT LIKE '%borrow invoice%'
        """
    )


def downgrade():
    # This is a one-way correction of persisted receipt state. Resetting invoices
    # to unpaid would undo real business state and cannot be safely automated.
    pass
