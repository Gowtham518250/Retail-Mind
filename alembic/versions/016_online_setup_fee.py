"""Add online-only setup fee configuration and order snapshot.

Revision ID: 016_online_setup_fee
Revises: 015_add_ai_query_history
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "016_online_setup_fee"
down_revision = "015_add_ai_query_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_profiles",
        sa.Column(
            "online_setup_fee",
            sa.Numeric(10, 2),
            nullable=False,
            server_default="0",
        ),
    )
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
    op.drop_column("online_orders", "online_setup_fee")
    op.drop_column("shop_profiles", "online_setup_fee")
