"""Persist online-store configuration per shop.

Revision ID: 022_online_store_configuration
Revises: 021_online_order_lifecycle_reviews
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa


revision = "022_online_store_configuration"
down_revision = "021_online_order_lifecycle_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "shop_profiles",
        sa.Column("online_setup_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_min_order", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_offer_delivery", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_offer_pickup", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_accept_cod", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("online_accept_online", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("shop_profiles", "online_accept_online")
    op.drop_column("shop_profiles", "online_accept_cod")
    op.drop_column("shop_profiles", "online_offer_pickup")
    op.drop_column("shop_profiles", "online_offer_delivery")
    op.drop_column("shop_profiles", "online_delivery_fee")
    op.drop_column("shop_profiles", "online_min_order")
    op.drop_column("shop_profiles", "online_setup_fee")
