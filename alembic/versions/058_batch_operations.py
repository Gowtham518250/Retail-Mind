"""Create the legacy batch-operation tracking table when absent.

Revision ID: 058_batch_operations
Revises: 057_customer_auth_and_whatsapp_orders
"""
from alembic import op
import sqlalchemy as sa


revision = "058_batch_operations"
down_revision = "057_customer_auth_and_whatsapp_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "batch_operations" in tables:
        return

    op.create_table(
        "batch_operations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True, server_default="PROCESSING"),
        sa.Column("total_records", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("processed_records", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("failed_records", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("errors", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("operation_metadata", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Preserve existing batch-operation history during rollbacks.
    pass
