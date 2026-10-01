"""Retail Growth Suite schema.

Revision ID: 019_retail_growth_suite
Revises: 018_repair_shop_active_flags
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "019_retail_growth_suite"
down_revision = "018_repair_shop_active_flags"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _add(bind, table, column, type_, nullable=True, default=None):
    if table not in sa.inspect(bind).get_table_names():
        return
    if column in _columns(bind, table):
        return
    kwargs = {"nullable": nullable}
    if default is not None:
        kwargs["server_default"] = str(default)
    op.add_column(table, sa.Column(column, type_, **kwargs))


def upgrade():
    bind = op.get_bind()

    # New core growth-suite tables.
    op.create_table(
        "retail_branches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("phone", sa.String(30)),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("owner_id", "code", name="uix_branch_owner_code"),
    )
    op.create_index("ix_retail_branches_owner_id", "retail_branches", ["owner_id"])

    op.create_table(
        "online_order_returns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("online_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("online_customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="REQUESTED"),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("stock_restored", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("customer_note", sa.Text()),
        sa.Column("owner_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime()),
    )
    op.create_index("ix_online_order_returns_order_id", "online_order_returns", ["order_id"])
    op.create_index("ix_online_order_returns_shop_id", "online_order_returns", ["shop_id"])
    op.create_index("ix_online_order_returns_customer_id", "online_order_returns", ["customer_id"])

    op.create_table(
        "retail_coupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("discount_type", sa.String(20), nullable=False, server_default="PERCENT"),
        sa.Column("discount_value", sa.Numeric(12,2), nullable=False),
        sa.Column("minimum_order_amount", sa.Numeric(12,2), nullable=False, server_default="0"),
        sa.Column("maximum_discount", sa.Numeric(12,2)),
        sa.Column("usage_limit", sa.Integer()),
        sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shop_id", "code", name="uix_coupon_shop_code"),
    )

    op.create_table(
        "online_customer_loyalty",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("online_customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("points_balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_earned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lifetime_redeemed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tier", sa.String(30), nullable=False, server_default="Member"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("customer_id", "shop_id", name="uix_online_loyalty_customer_shop"),
    )

    op.create_table(
        "online_loyalty_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("loyalty_id", sa.Integer(), sa.ForeignKey("online_customer_loyalty.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("online_orders.id", ondelete="SET NULL")),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "online_delivery_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("online_orders.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
        sa.Column("driver_name", sa.String(100), nullable=False),
        sa.Column("driver_phone", sa.String(30)),
        sa.Column("status", sa.String(30), nullable=False, server_default="ASSIGNED"),
        sa.Column("notes", sa.Text()),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("picked_up_at", sa.DateTime()),
        sa.Column("delivered_at", sa.DateTime()),
    )

    # Compatibility columns on pre-existing tables.
    _add(bind, "products", "branch_id", sa.Integer())
    _add(bind, "invoices", "branch_id", sa.Integer())
    _add(bind, "purchase_orders", "branch_id", sa.Integer())
    _add(bind, "shop_expenses", "branch_id", sa.Integer())
    _add(bind, "online_orders", "branch_id", sa.Integer())
    _add(bind, "online_orders", "coupon_code", sa.String(50))
    _add(bind, "online_orders", "discount_amount", sa.Numeric(12,2), nullable=False, default=0)


def downgrade():
    for table in [
        "online_delivery_assignments",
        "online_loyalty_transactions",
        "online_customer_loyalty",
        "retail_coupons",
        "online_order_returns",
        "retail_branches",
    ]:
        op.drop_table(table)
