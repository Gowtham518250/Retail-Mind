"""Persist owner-scoped Grow My Shop campaign drafts.

Revision ID: 048_growth_marketing_campaigns
Revises: 047_online_order_shop_status_index
"""
from alembic import op
import sqlalchemy as sa

revision = "048_growth_marketing_campaigns"
down_revision = "047_online_order_shop_status_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "growth_marketing_campaigns" not in tables:
        op.create_table(
            "growth_marketing_campaigns",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "shop_id",
                sa.Integer(),
                sa.ForeignKey("user_details.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("campaign_key", sa.String(length=64), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=True),
            sa.Column("product_name", sa.String(length=120), nullable=True),
            sa.Column("product_price", sa.Numeric(12, 2), nullable=True),
            sa.Column("goal", sa.String(length=32), nullable=False),
            sa.Column("language", sa.String(length=8), nullable=False, server_default="en"),
            sa.Column("ad_format", sa.String(length=16), nullable=False, server_default="feed"),
            sa.Column("template", sa.String(length=32), nullable=False, server_default="bold"),
            sa.Column("shop_name", sa.String(length=200), nullable=False),
            sa.Column("headline", sa.String(length=120), nullable=False),
            sa.Column("caption", sa.Text(), nullable=False),
            sa.Column("offer", sa.String(length=90), nullable=False, server_default=""),
            sa.Column("offer_code", sa.String(length=32), nullable=False, server_default=""),
            sa.Column("generation_source", sa.String(length=32), nullable=False, server_default="manual"),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="DRAFT"),
            sa.Column("redemptions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("shop_id", "campaign_key", name="uq_growth_campaign_shop_key"),
        )
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("growth_marketing_campaigns")}
    if "ix_growth_campaigns_shop_updated" not in indexes:
        op.create_index(
            "ix_growth_campaigns_shop_updated",
            "growth_marketing_campaigns",
            ["shop_id", "updated_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "growth_marketing_campaigns" in set(sa.inspect(bind).get_table_names()):
        op.drop_table("growth_marketing_campaigns")
