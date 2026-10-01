"""Add marketplace ratings, verified shop reviews, and merge migration heads.

Revision ID: 014_marketplace_reviews_and_ratings
Revises: 013_add_online_order_delivery_otps, e7a9054db41d
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa

revision = "014_marketplace_reviews_and_ratings"
down_revision = ("013_add_online_order_delivery_otps", "e7a9054db41d")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shop_profiles",
        sa.Column("rating_score", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "shop_profiles",
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "shop_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("online_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shop_id",
            sa.Integer(),
            sa.ForeignKey("user_details.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("online_customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_shop_reviews_rating"),
        sa.UniqueConstraint("order_id", name="uq_shop_reviews_order_id"),
    )
    op.create_index("ix_shop_profiles_rating_score", "shop_profiles", ["rating_score"])
    op.create_index("ix_shop_reviews_shop_id", "shop_reviews", ["shop_id"])
    op.create_index("ix_shop_reviews_customer_id", "shop_reviews", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_shop_reviews_customer_id", table_name="shop_reviews")
    op.drop_index("ix_shop_reviews_shop_id", table_name="shop_reviews")
    op.drop_table("shop_reviews")
    op.drop_index("ix_shop_profiles_rating_score", table_name="shop_profiles")
    op.drop_column("shop_profiles", "rating_count")
    op.drop_column("shop_profiles", "rating_score")
