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
    # 🔧 FIX: Add unique constraint on (user_id, offline_id) for idempotency
    # This prevents duplicate syncs of the same offline sale
    op.create_unique_constraint(
        'uix_user_offline_id',
        'invoices',
        ['user_id', 'offline_id']
    )


def downgrade():
    # Remove the unique constraint
    op.drop_constraint('uix_user_offline_id', 'invoices', type_='unique')
