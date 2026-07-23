"""Add unique constraint on (user_id, offline_id) for invoices

Revision ID: 003
Revises: 002
Create Date: 2026-06-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002_add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    # ==================== PRE-FLIGHT ====================
    # Ensure offline_id exists before creating the constraint
    op.execute("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS offline_id VARCHAR(50)")
    
    # 🔧 FIX: Add unique constraint on (user_id, offline_id) for idempotency
    # This prevents duplicate syncs of the same offline sale.
    # We use a DO block to make it safe on re-runs or fresh databases.
    op.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uix_user_offline_id') THEN
                ALTER TABLE invoices ADD CONSTRAINT uix_user_offline_id UNIQUE (user_id, offline_id);
            END IF;
        END $$;
    """)


def downgrade():
    # Remove the unique constraint
    op.drop_constraint('uix_user_offline_id', 'invoices', type_='unique')
