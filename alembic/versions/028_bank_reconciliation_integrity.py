"""Add idempotency and timestamps to bank reconciliation records.

Revision ID: 028_bank_reconciliation_integrity
Revises: 027_purchase_order_receiving
"""
from alembic import op
import sqlalchemy as sa

revision = "028_bank_reconciliation_integrity"
down_revision = "027_purchase_order_receiving"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "bank_reconciliations",
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "bank_reconciliations",
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "uq_bank_reconciliation_shop_idempotency",
        "bank_reconciliations",
        ["shop_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
        sqlite_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade():
    op.drop_index(
        "uq_bank_reconciliation_shop_idempotency",
        table_name="bank_reconciliations",
    )
    op.drop_column("bank_reconciliations", "created_at")
    op.drop_column("bank_reconciliations", "idempotency_key")
