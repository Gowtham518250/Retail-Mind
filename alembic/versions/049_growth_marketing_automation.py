"""Add Grow My Shop offer facts, approval versions and automation triggers.

Revision ID: 049_growth_marketing_automation
Revises: 048_growth_marketing_campaigns
"""
from alembic import op
import sqlalchemy as sa

revision = "049_growth_marketing_automation"
down_revision = "048_growth_marketing_campaigns"
branch_labels = None
depends_on = None


CAMPAIGN_COLUMNS = (
    ("original_price", sa.Numeric(12, 2)),
    ("discount_price", sa.Numeric(12, 2)),
    ("discount_percent", sa.Numeric(6, 2)),
    ("offer_valid_from", sa.Date()),
    ("offer_valid_until", sa.Date()),
    ("shop_address", sa.Text()),
    ("shop_location", sa.String(300)),
    ("shop_city", sa.String(100)),
    ("shop_state", sa.String(100)),
    ("shop_postal_code", sa.String(10)),
    ("shop_latitude", sa.Float()),
    ("shop_longitude", sa.Float()),
    ("shop_phone", sa.String(20)),
    ("shop_website", sa.String(200)),
    ("shop_logo_url", sa.String(500)),
    ("trigger_type", sa.String(32), "manual"),
    ("content_version", sa.Integer(), 1),
    ("approved_version", sa.Integer()),
    ("approved_by", sa.Integer()),
    ("approved_at", sa.DateTime()),
    ("rejected_reason", sa.Text()),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "growth_marketing_campaigns" in tables:
        existing = {column["name"] for column in inspector.get_columns("growth_marketing_campaigns")}
        for item in CAMPAIGN_COLUMNS:
            name, column_type = item[0], item[1]
            if name not in existing:
                kwargs = {"nullable": True}
                if len(item) == 3:
                    kwargs["nullable"] = False
                    kwargs["server_default"] = str(item[2])
                op.add_column("growth_marketing_campaigns", sa.Column(name, column_type, **kwargs))

    if "growth_marketing_automation_settings" not in tables:
        op.create_table(
            "growth_marketing_automation_settings",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("new_products_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("weekly_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("weekly_day", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("language", sa.String(8), nullable=False, server_default="en"),
            sa.Column("max_campaigns_per_week", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("shop_id", name="uq_growth_marketing_settings_shop"),
        )

    if "growth_marketing_triggers" not in tables:
        op.create_table(
            "growth_marketing_triggers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("trigger_key", sa.String(128), nullable=False),
            sa.Column("trigger_type", sa.String(32), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("shop_id", "trigger_key", name="uq_growth_marketing_trigger_key"),
        )
        op.create_index(
            "ix_growth_marketing_triggers_status_created",
            "growth_marketing_triggers",
            ["status", "created_at"],
            unique=False,
        )
        op.create_index(
            "ix_growth_marketing_triggers_shop_status",
            "growth_marketing_triggers",
            ["shop_id", "status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "growth_marketing_triggers" in tables:
        op.drop_table("growth_marketing_triggers")
    if "growth_marketing_automation_settings" in tables:
        op.drop_table("growth_marketing_automation_settings")
    if "growth_marketing_campaigns" in tables:
        existing = {column["name"] for column in sa.inspect(bind).get_columns("growth_marketing_campaigns")}
        for item in reversed(CAMPAIGN_COLUMNS):
            if item[0] in existing:
                op.drop_column("growth_marketing_campaigns", item[0])
