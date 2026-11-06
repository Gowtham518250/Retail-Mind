"""Add Cashfree PG identifiers to customer online orders.

Revision ID: 045_cashfree_online_order_payments
Revises: 044_upi_reservation_expiry_index
"""
from alembic import op
import sqlalchemy as sa


revision = "045_cashfree_online_order_payments"
down_revision = "044_upi_reservation_expiry_index"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "online_orders" not in inspector.get_table_names():
        return

    columns = {item["name"] for item in inspector.get_columns("online_orders")}
    if "cashfree_order_id" not in columns:
        op.add_column(
            "online_orders",
            sa.Column("cashfree_order_id", sa.String(length=45), nullable=True),
        )
    if "cashfree_payment_session_id" not in columns:
        op.add_column(
            "online_orders",
            sa.Column("cashfree_payment_session_id", sa.Text(), nullable=True),
        )
    if "cashfree_payment_id" not in columns:
        op.add_column(
            "online_orders",
            sa.Column("cashfree_payment_id", sa.String(length=128), nullable=True),
        )

    indexes = {
        item.get("name") for item in sa.inspect(connection).get_indexes("online_orders")
    }
    if "uq_online_orders_cashfree_order_id" not in indexes:
        op.create_index(
            "uq_online_orders_cashfree_order_id",
            "online_orders",
            ["cashfree_order_id"],
            unique=True,
            postgresql_where=sa.text("cashfree_order_id IS NOT NULL"),
            sqlite_where=sa.text("cashfree_order_id IS NOT NULL"),
        )
    if "uq_online_orders_cashfree_payment_id" not in indexes:
        op.create_index(
            "uq_online_orders_cashfree_payment_id",
            "online_orders",
            ["cashfree_payment_id"],
            unique=True,
            postgresql_where=sa.text("cashfree_payment_id IS NOT NULL"),
            sqlite_where=sa.text("cashfree_payment_id IS NOT NULL"),
        )


def downgrade():
    connection = op.get_bind()
    if "online_orders" not in sa.inspect(connection).get_table_names():
        return
    indexes = {
        item.get("name") for item in sa.inspect(connection).get_indexes("online_orders")
    }
    if "uq_online_orders_cashfree_payment_id" in indexes:
        op.drop_index("uq_online_orders_cashfree_payment_id", table_name="online_orders")
    if "uq_online_orders_cashfree_order_id" in indexes:
        op.drop_index("uq_online_orders_cashfree_order_id", table_name="online_orders")

    columns = {item["name"] for item in sa.inspect(connection).get_columns("online_orders")}
    if "cashfree_payment_id" in columns:
        op.drop_column("online_orders", "cashfree_payment_id")
    if "cashfree_payment_session_id" in columns:
        op.drop_column("online_orders", "cashfree_payment_session_id")
    if "cashfree_order_id" in columns:
        op.drop_column("online_orders", "cashfree_order_id")
