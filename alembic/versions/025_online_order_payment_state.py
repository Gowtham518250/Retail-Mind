"""Persist online-order payment method and notification reconciliation state.

Revision ID: 025_online_order_payment_state
Revises: 024_customer_sync_feed
"""
from alembic import op
import sqlalchemy as sa


revision = "025_online_order_payment_state"
down_revision = "024_customer_sync_feed"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "online_orders",
        sa.Column("payment_method", sa.String(length=20), nullable=False, server_default="COD"),
    )
    op.add_column(
        "online_orders",
        sa.Column("payment_status", sa.String(length=24), nullable=False, server_default="COD_DUE"),
    )
    op.add_column(
        "online_orders",
        sa.Column("payment_reference", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "online_orders",
        sa.Column("payment_detection_key", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "online_orders",
        sa.Column("payment_confirmed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_online_order_shop_payment_key",
        "online_orders",
        ["shop_id", "payment_detection_key"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_online_order_shop_payment_key", table_name="online_orders")
    op.drop_column("online_orders", "payment_confirmed_at")
    op.drop_column("online_orders", "payment_detection_key")
    op.drop_column("online_orders", "payment_reference")
    op.drop_column("online_orders", "payment_status")
    op.drop_column("online_orders", "payment_method")
