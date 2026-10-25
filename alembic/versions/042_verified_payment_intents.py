"""Create invoice-bound payment intents for signed bank/PSP confirmation.

Revision ID: 042_verified_payment_intents
Revises: 041_cancelled_online_order_financial_cleanup, e7a9054db41d

The intent captures the exact outstanding INR amount and shop destination at
creation time. Only a trusted callback with a valid HMAC, matching provider
transaction, amount, and destination can move it to PAID.
"""
from alembic import op
import sqlalchemy as sa


revision = "042_verified_payment_intents"
down_revision = ("041_cancelled_online_order_financial_cleanup", "e7a9054db41d")
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "verified_payment_intents" not in tables:
        op.create_table(
            "verified_payment_intents",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("public_reference", sa.String(length=64), nullable=False),
            sa.Column("shop_id", sa.Integer(), nullable=False),
            sa.Column("invoice_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False, server_default="bank_psp"),
            sa.Column("amount_paise", sa.BigInteger(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
            sa.Column("destination_vpa", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="PENDING"),
            sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["shop_id"], ["user_details.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "provider",
                "provider_transaction_id",
                name="uq_verified_payment_provider_txn",
            ),
        )

    inspector = sa.inspect(bind)
    if "verified_payment_intents" not in set(inspector.get_table_names()):
        raise RuntimeError("verified_payment_intents table was not created")

    indexes = {
        index["name"]: index
        for index in sa.inspect(bind).get_indexes("verified_payment_intents")
    }
    index_specs = (
        ("ix_verified_payment_intents_public_reference", ["public_reference"], True),
        ("ix_verified_payment_intents_shop_id", ["shop_id"], False),
        ("ix_verified_payment_intents_invoice_id", ["invoice_id"], False),
        ("ix_verified_payment_intents_status", ["status"], False),
        ("ix_verified_payment_shop_invoice_status", ["shop_id", "invoice_id", "status"], False),
    )
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("verified_payment_intents")
    }
    for name, column_names, unique in index_specs:
        if name not in indexes and all(column in columns for column in column_names):
            op.create_index(
                name,
                "verified_payment_intents",
                column_names,
                unique=unique,
            )


def downgrade() -> None:
    # Retain verification records: removing them would erase financial audit
    # evidence and could permit provider transaction IDs to be reused.
    pass
