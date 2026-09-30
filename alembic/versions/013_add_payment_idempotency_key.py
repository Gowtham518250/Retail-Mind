"""Add durable payment idempotency key

Revision ID: 013_add_payment_idempotency_key
Revises: 012_add_invoice_sold_by_worker
Create Date: 2026-09-30

"""
from alembic import op

revision = '013_add_payment_idempotency_key'
down_revision = '012_add_invoice_sold_by_worker'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        'ALTER TABLE payments ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128)'
    )
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_payments_idempotency_key ON payments (idempotency_key) WHERE idempotency_key IS NOT NULL'
    )
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_payments_reference_number ON payments (reference_number)'
    )


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS ix_payments_reference_number')
    op.execute('DROP INDEX IF EXISTS uq_payments_idempotency_key')
    op.execute(
        'ALTER TABLE payments DROP COLUMN IF EXISTS idempotency_key'
    )