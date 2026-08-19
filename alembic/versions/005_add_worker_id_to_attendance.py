"""Add worker_id to attendance table

Revision ID: 005_add_worker_id_to_attendance
Revises: 004_add_timestamps_to_shop_models
Create Date: 2026-07-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '005_add_worker_id_to_attendance'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS worker_id INTEGER")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_attendance_worker_id'
                  AND conrelid = 'attendance'::regclass
            ) THEN
                ALTER TABLE attendance
                ADD CONSTRAINT fk_attendance_worker_id
                FOREIGN KEY (worker_id) REFERENCES workers(id)
                ON DELETE SET NULL;
            END IF;
        END
        $$;
    """)
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uix_employee_date')
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uix_employee_date_worker'
                  AND conrelid = 'attendance'::regclass
            ) THEN
                ALTER TABLE attendance
                ADD CONSTRAINT uix_employee_date_worker
                UNIQUE (employee_id, attendance_date, worker_id);
            END IF;
        END
        $$;
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS uix_employee_date_worker')
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uix_employee_date'
                  AND conrelid = 'attendance'::regclass
            ) THEN
                ALTER TABLE attendance
                ADD CONSTRAINT uix_employee_date
                UNIQUE (employee_id, attendance_date);
            END IF;
        END
        $$;
    """)
    op.execute('ALTER TABLE attendance DROP CONSTRAINT IF EXISTS fk_attendance_worker_id')
    op.execute('ALTER TABLE attendance DROP COLUMN IF EXISTS worker_id')
