"""Repair production schemas for marketplace ratings and online setup fees.

Revision ID: 017_repair_marketplace_schema
Revises: 016_online_setup_fee
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "017_repair_marketplace_schema"
down_revision = "016_online_setup_fee"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column):
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "shop_profiles" in inspector.get_table_names():
        if not _has_column(inspector, "shop_profiles", "rating_score"):
            op.add_column(
                "shop_profiles",
                sa.Column("rating_score", sa.Float(), nullable=False, server_default="0"),
            )
        if not _has_column(inspector, "shop_profiles", "rating_count"):
            op.add_column(
                "shop_profiles",
                sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
            )
        if not _has_column(inspector, "shop_profiles", "online_setup_fee"):
            op.add_column(
                "shop_profiles",
                sa.Column(
                    "online_setup_fee",
                    sa.Numeric(10, 2),
                    nullable=False,
                    server_default="0",
                ),
            )

    inspector = sa.inspect(bind)
    if "online_orders" in inspector.get_table_names() and not _has_column(
        inspector, "online_orders", "online_setup_fee"
    ):
        op.add_column(
            "online_orders",
            sa.Column(
                "online_setup_fee",
                sa.Numeric(10, 2),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "online_orders" in inspector.get_table_names() and _has_column(
        inspector, "online_orders", "online_setup_fee"
    ):
        op.drop_column("online_orders", "online_setup_fee")

    inspector = sa.inspect(bind)
    if "shop_profiles" in inspector.get_table_names():
        if _has_column(inspector, "shop_profiles", "online_setup_fee"):
            op.drop_column("shop_profiles", "online_setup_fee")
        if _has_column(inspector, "shop_profiles", "rating_count"):
            op.drop_column("shop_profiles", "rating_count")
        if _has_column(inspector, "shop_profiles", "rating_score"):
            op.drop_column("shop_profiles", "rating_score")
