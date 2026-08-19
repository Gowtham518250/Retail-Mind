"""Add worker_id to attendance table

Revision ID: 005_add_worker_id_to_attendance
Revises: 004_add_timestamps_to_shop_models
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005_add_worker_id_to_attendance'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Existing production databases may already contain worker_id and its
    # foreign key because the ORM schema was created before this migration.
    columns = {column['name'] for column in inspector.get_columns('attendance')}
    if 'worker_id' not in columns:
        op.add_column('attendance', sa.Column('worker_id', sa.Integer(), nullable=True))
        inspector = sa.inspect(bind)

    foreign_keys = inspector.get_foreign_keys('attendance')
    has_worker_fk = any(
        fk.get('constrained_columns') == ['worker_id']
        and fk.get('referred_table') == 'workers'
        for fk in foreign_keys
    )
    if not has_worker_fk:
        op.create_foreign_key(
            'fk_attendance_worker_id',
            'attendance', 'workers',
            ['worker_id'], ['id'],
            ondelete='SET NULL'
        )

    # Remove the legacy employee/date-only constraint when present.
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uix_employee_date')

    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints('attendance')
    has_worker_unique = any(
        set(constraint.get('column_names', []))
        == {'employee_id', 'attendance_date', 'worker_id'}
        for constraint in unique_constraints
    )
    if not has_worker_unique:
        op.create_unique_constraint(
            'uix_employee_date_worker',
            'attendance',
            ['employee_id', 'attendance_date', 'worker_id']
        )


def downgrade() -> None:
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uix_employee_date_worker')
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS fk_attendance_worker_id')

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints('attendance')
    has_old_unique = any(
        set(constraint.get('column_names', []))
        == {'employee_id', 'attendance_date'}
        for constraint in unique_constraints
    )
    if not has_old_unique:
        op.create_unique_constraint(
            'uix_employee_date',
            'attendance',
            ['employee_id', 'attendance_date']
        )

    columns = {column['name'] for column in inspector.get_columns('attendance')}
    if 'worker_id' in columns:
        op.drop_column('attendance', 'worker_id')
