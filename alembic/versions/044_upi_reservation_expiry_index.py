"""Index unpaid UPI orders used by the reservation-expiry worker.

Revision ID: 044_upi_reservation_expiry_index
Revises: 043_retailmind_subscriptions
"""
from alembic import op
import sqlalchemy as sa


revision = "044_upi_reservation_expiry_index"
down_revision = "043_retailmind_subscriptions"
branch_labels = None
depends_on = None


_INDEX_NAME = "ix_online_orders_upi_pending_reservation"
_PREDICATE = sa.text(
    "payment_method = 'UPI' AND payment_status = 'PENDING' "
    "AND order_status IN ('PENDING', 'ACCEPTED')"
)


def upgrade():
    connection = op.get_bind()
    if "online_orders" not in sa.inspect(connection).get_table_names():
        return

    existing_indexes = {
        item.get("name")
        for item in sa.inspect(connection).get_indexes("online_orders")
    }
    if _INDEX_NAME not in existing_indexes:
        op.create_index(
            _INDEX_NAME,
            "online_orders",
            ["created_at"],
            unique=False,
            postgresql_where=_PREDICATE,
            sqlite_where=_PREDICATE,
        )


def downgrade():
    connection = op.get_bind()
    if "online_orders" not in sa.inspect(connection).get_table_names():
        return
    existing_indexes = {
        item.get("name")
        for item in sa.inspect(connection).get_indexes("online_orders")
    }
    if _INDEX_NAME in existing_indexes:
        op.drop_index(_INDEX_NAME, table_name="online_orders")
