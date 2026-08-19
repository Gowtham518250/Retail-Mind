"""Make owner/shopkeeper self-attendance unique per day.

Revision ID: 008_attendance_nullsafe_unique
Revises: 007_merge_migration_heads
Create Date: 2026-08-19 00:00:00.000000
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
