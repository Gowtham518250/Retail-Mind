"""Add idempotency keys to stock movements.

Revision ID: 031_stock_movement_idempotency
Revises: 030_regular_cash_paid_state

Legacy stock movement rows remain valid with a NULL key. New stock deductions
persist a stable key so request retries cannot create a second deduction.
"""
from alembic import op
import sqlalchemy as sa

revision = "031_stock_movement_idempotency"
down_revision = "030_regular_cash_paid_state"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "stock_movements",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_stock_movement_idempotency_key",
        "stock_movements",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_stock_movement_idempotency_key",
        table_name="stock_movements",
    )
    op.drop_column("stock_movements", "idempotency_key")
