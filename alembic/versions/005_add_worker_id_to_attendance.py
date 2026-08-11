"""Add worker_id to attendance table

Revision ID: 005_add_worker_id_to_attendance
Revises: 004_add_timestamps_to_shop_models
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_worker_id_to_attendance'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add worker_id column to attendance table
    op.add_column('attendance', sa.Column('worker_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint to workers table
    op.create_foreign_key(
        'fk_attendance_worker_id',
        'attendance', 'workers',
        ['worker_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Update unique constraint to include worker_id
    # First drop the old constraint if it exists
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uix_employee_date')
    
    # Add new unique constraint including worker_id
    op.create_unique_constraint(
        'uix_employee_date_worker',
        'attendance',
        ['employee_id', 'attendance_date', 'worker_id']
    )


def downgrade() -> None:
    # Remove the new unique constraint
    op.drop_constraint('uix_employee_date_worker', 'attendance', type_='unique')
    
    # Restore old unique constraint
    op.create_unique_constraint(
        'uix_employee_date',
        'attendance',
        ['employee_id', 'attendance_date']
    )
    
    # Remove foreign key
    op.drop_constraint('fk_attendance_worker_id', 'attendance', type_='foreignkey')
    
    # Remove worker_id column
    op.drop_column('attendance', 'worker_id')
