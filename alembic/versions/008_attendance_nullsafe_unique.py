"""Make owner/shopkeeper self-attendance unique per day.

Revision ID: 008_attendance_nullsafe_unique
Revises: 007_merge_migration_heads
Create Date: 2026-08-19 00:00:00.000000

PostgreSQL treats NULL values as distinct for normal UNIQUE constraints.
Migration 005 therefore protects worker rows (worker_id is non-NULL) but does
not prevent two owner/shopkeeper self-check-in rows where worker_id is NULL.

This migration adds a partial unique index covering only those self rows.
Existing worker uniqueness remains provided by uix_employee_date_worker.

Before applying in production, check for existing duplicates:

    SELECT employee_id, attendance_date, COUNT(*)
    FROM attendance
    WHERE worker_id IS NULL
    GROUP BY employee_id, attendance_date
    HAVING COUNT(*) > 1;

If rows are returned, reconcile those duplicates before running this migration;
the CREATE UNIQUE INDEX must not silently delete attendance history.
"""

from alembic import op

revision = "008_attendance_nullsafe_unique"
down_revision = "007_merge_migration_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uix_attendance_owner_employee_date
        ON attendance (employee_id, attendance_date)
        WHERE worker_id IS NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS uix_attendance_owner_employee_date"
    )
