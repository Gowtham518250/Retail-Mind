"""Add sold_by_worker_id to invoices (staff sales leaderboard)

Revision ID: 012_add_invoice_sold_by_worker
Revises: 011_force_invoice_line_discount_schema
Create Date: 2026-08-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012_add_invoice_sold_by_worker'
down_revision = '011_force_invoice_line_discount_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable, purely additive - every existing invoice row gets NULL
    # (no attributed worker), which is the correct/expected value for
    # sales made before this feature existed or made directly by the
    # owner. Safe to resume if partially applied already.
    op.execute(
        "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS sold_by_worker_id INTEGER"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_invoices_sold_by_worker_id'
                  AND conrelid = 'invoices'::regclass
            ) THEN
                ALTER TABLE invoices
                ADD CONSTRAINT fk_invoices_sold_by_worker_id
                FOREIGN KEY (sold_by_worker_id) REFERENCES workers(id)
                ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_invoices_sold_by_worker_id ON invoices (sold_by_worker_id)"
    )


def downgrade() -> None:
    op.execute(
        'DROP INDEX IF EXISTS ix_invoices_sold_by_worker_id'
    )
    op.execute(
        'ALTER TABLE invoices DROP CONSTRAINT IF EXISTS fk_invoices_sold_by_worker_id'
    )
    op.execute(
        'ALTER TABLE invoices DROP COLUMN IF EXISTS sold_by_worker_id'
    )
