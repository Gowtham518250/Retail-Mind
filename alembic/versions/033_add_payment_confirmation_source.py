"""Persist the origin of notification-based online-order payment matches.

Revision ID: 033_add_payment_confirmation_source
Revises: 032_restore_sales_journal_event_time
"""
from alembic import op
import sqlalchemy as sa

revision = "033_add_payment_confirmation_source"
down_revision = "032_restore_sales_journal_event_time"
branch_labels = None
depends_on = None


def upgrade():
    # Startup compatibility migrations may already have added the column on a
    # legacy deployment. Inspect first so Alembic remains safe in either order.
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("online_orders")}
    if "payment_confirmation_source" not in columns:
        op.add_column(
            "online_orders",
            sa.Column("payment_confirmation_source", sa.String(length=50), nullable=True),
        )


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("online_orders")}
    if "payment_confirmation_source" in columns:
        op.drop_column("online_orders", "payment_confirmation_source")
