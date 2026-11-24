"""Allow name-only Khata customers with per-shop uniqueness.

Revision ID: 055_khata_name_only_accounts
Revises: 054_agentic_khata_ledger_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "055_khata_name_only_accounts"
down_revision = "054_agentic_khata_ledger_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "khata_balances" not in tables:
        raise RuntimeError("khata_balances is missing; refusing to enable name-only Khata accounts")

    columns = {
        column["name"]: column
        for column in inspector.get_columns("khata_balances")
    }
    phone_column = columns.get("customer_phone")
    if phone_column is None:
        raise RuntimeError("khata_balances.customer_phone is missing")
    if not phone_column.get("nullable", False):
        op.alter_column(
            "khata_balances",
            "customer_phone",
            existing_type=sa.String(length=20),
            nullable=True,
        )

    # Name-only rows are unique by normalized customer name within a shop.
    # Phone-backed legacy rows remain governed by uix_shop_customer_khata.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_shop_name_only_khata
        ON khata_balances (shop_id, lower(customer_name))
        WHERE customer_phone IS NULL
          AND customer_name IS NOT NULL
          AND btrim(customer_name) <> ''
        """
    )


def downgrade() -> None:
    # Keep the nullable phone column: deployments may already contain valid
    # name-only ledger rows, and making it NOT NULL would risk production data.
    op.execute("DROP INDEX IF EXISTS uq_shop_name_only_khata")
