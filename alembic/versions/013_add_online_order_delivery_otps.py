"""Add customer OTP challenges for online order delivery verification.

Revision ID: 013_add_online_order_delivery_otps
Revises: 012_add_invoice_sold_by_worker
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "013_add_online_order_delivery_otps"
down_revision = "012_add_invoice_sold_by_worker"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "online_order_delivery_otps",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("online_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.Integer(),
            sa.ForeignKey("online_customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("otp_hash", sa.String(length=128), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_online_order_delivery_otps_order_id",
        "online_order_delivery_otps",
        ["order_id"],
    )
    op.create_index(
        "ix_online_order_delivery_otps_customer_id",
        "online_order_delivery_otps",
        ["customer_id"],
    )
    op.create_index(
        "ix_online_order_delivery_otps_otp_expires_at",
        "online_order_delivery_otps",
        ["otp_expires_at"],
    )
    op.create_index(
        "ix_online_order_delivery_otps_used",
        "online_order_delivery_otps",
        ["used"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_online_order_delivery_otps_used",
        table_name="online_order_delivery_otps",
    )
    op.drop_index(
        "ix_online_order_delivery_otps_otp_expires_at",
        table_name="online_order_delivery_otps",
    )
    op.drop_index(
        "ix_online_order_delivery_otps_customer_id",
        table_name="online_order_delivery_otps",
    )
    op.drop_index(
        "ix_online_order_delivery_otps_order_id",
        table_name="online_order_delivery_otps",
    )
    op.drop_table("online_order_delivery_otps")
