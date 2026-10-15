"""Add idempotency for offline/manual expense submissions.

Revision ID: 029_expense_idempotency
Revises: 028_bank_reconciliation_integrity
"""
from alembic import op
import sqlalchemy as sa

revision = "029_expense_idempotency"
down_revision = "028_bank_reconciliation_integrity"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "shop_expenses",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "uq_shop_expense_shop_idempotency",
        "shop_expenses",
        ["shop_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_shop_expense_shop_idempotency",
        table_name="shop_expenses",
    )
    op.drop_column("shop_expenses", "idempotency_key")
