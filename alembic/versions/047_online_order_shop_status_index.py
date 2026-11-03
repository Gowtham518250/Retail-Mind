"""Index online orders by tenant and lifecycle status.

Revision ID: 047_online_order_shop_status_index
Revises: 046_payment_detection_evidence
"""
from alembic import op
import sqlalchemy as sa

revision = "047_online_order_shop_status_index"
down_revision = "046_payment_detection_evidence"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_online_orders_shop_status"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "online_orders" not in set(inspector.get_table_names()):
        raise RuntimeError("Required online_orders table is missing.")
    indexes = {item["name"] for item in inspector.get_indexes("online_orders")}
    if INDEX_NAME not in indexes:
        op.create_index(
            INDEX_NAME,
            "online_orders",
            ["shop_id", "order_status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "online_orders" not in set(inspector.get_table_names()):
        return
    indexes = {item["name"] for item in inspector.get_indexes("online_orders")}
    if INDEX_NAME in indexes:
        op.drop_index(INDEX_NAME, table_name="online_orders")
