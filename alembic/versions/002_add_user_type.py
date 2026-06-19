"""add user_type to user_details for role-based routing

Revision ID: 002_add_user_type
Revises: 001_initial_schema
Create Date: 2026-06-19

Adds a persistent ``user_type`` column to ``user_details`` so that login can
derive the account role (OWNER / CUSTOMER / WORKER / DELIVERY) from the stored
record instead of from whichever endpoint was called. This fixes customers being
routed to the Owner dashboard and registration collisions across roles.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_add_user_type'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user_details',
        sa.Column('user_type', sa.String(length=20), nullable=False, server_default='OWNER'),
    )
    op.create_index('ix_user_details_user_type', 'user_details', ['user_type'])


def downgrade() -> None:
    op.drop_index('ix_user_details_user_type', table_name='user_details')
    op.drop_column('user_details', 'user_type')
