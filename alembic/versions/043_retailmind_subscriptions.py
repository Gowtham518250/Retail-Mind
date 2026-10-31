"""Retail Mind four-tier subscriptions, Cashfree billing and daily AI quota."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "043_retailmind_subscriptions"
down_revision = "042_verified_payment_intents"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "rm_subscription_plans",
        sa.Column("plan_code", sa.String(24), primary_key=True),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("monthly_amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("yearly_amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("daily_ai_query_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "rm_shop_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_code", sa.String(24), sa.ForeignKey("rm_subscription_plans.plan_code"), nullable=False),
        sa.Column("billing_interval", sa.String(12), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("cashfree_subscription_id", sa.String(250), unique=True),
        sa.Column("subscription_session_id", sa.Text()),
        sa.Column("mandate_status", sa.String(32)),
        sa.Column("current_period_start", sa.DateTime()),
        sa.Column("current_period_end", sa.DateTime()),
        sa.Column("grace_period_end", sa.DateTime()),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cancelled_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_rm_shop_subscriptions_shop_created", "rm_shop_subscriptions", ["shop_id", "created_at"])
    op.create_table(
        "rm_subscription_payments",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.BigInteger(), sa.ForeignKey("rm_shop_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cashfree_payment_id", sa.String(128), unique=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("payment_type", sa.String(24), nullable=False, server_default="RENEWAL"),
        sa.Column("paid_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "rm_subscription_webhook_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("event_key", sa.String(128), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "rm_ai_daily_usage",
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("usage_date", sa.Date(), primary_key=True),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    plans = [
        ("FREE", "Free Starter", 0, 0, 0, {"sales": True, "khata": True, "attendance": True, "basic_inventory": True}),
        ("BASIC", "Basic", 9900, 99900, 7, {"sales": True, "khata": True, "attendance": True, "inventory": True, "basic_reports": True, "customer_management": True}),
        ("PRO", "Pro", 19900, 199900, 25, {"sales": True, "khata": True, "attendance": True, "inventory": True, "voice_billing": True, "barcode_scanning": True, "online_orders": True, "advanced_analytics": True, "customer_insights": True}),
        ("BUSINESS", "Business", 39900, 399900, 75, {"sales": True, "khata": True, "attendance": True, "inventory": True, "voice_billing": True, "barcode_scanning": True, "online_orders": True, "advanced_analytics": True, "customer_insights": True, "payment_announcements": True, "automated_reports": True, "advanced_ai_insights": True}),
    ]
    bind = op.get_bind()
    for code, name, monthly, yearly, daily, features in plans:
        bind.execute(sa.text("""
            INSERT INTO rm_subscription_plans
                (plan_code, name, monthly_amount_paise, yearly_amount_paise, daily_ai_query_limit, features)
            VALUES (:code, :name, :monthly, :yearly, :daily, CAST(:features AS jsonb))
            ON CONFLICT (plan_code) DO UPDATE SET
                name=EXCLUDED.name, monthly_amount_paise=EXCLUDED.monthly_amount_paise,
                yearly_amount_paise=EXCLUDED.yearly_amount_paise,
                daily_ai_query_limit=EXCLUDED.daily_ai_query_limit, features=EXCLUDED.features
        """), {"code": code, "name": name, "monthly": monthly, "yearly": yearly, "daily": daily, "features": __import__("json").dumps(features)})

def downgrade():
    op.drop_table("rm_ai_daily_usage")
    op.drop_table("rm_subscription_webhook_events")
    op.drop_table("rm_subscription_payments")
    op.drop_index("ix_rm_shop_subscriptions_shop_created", table_name="rm_shop_subscriptions")
    op.drop_table("rm_shop_subscriptions")
    op.drop_table("rm_subscription_plans")
