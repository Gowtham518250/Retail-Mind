"""Provision WhatsApp orders and online-customer password-reset tables.

Revision ID: 057_customer_auth_and_whatsapp_orders
Revises: 056_create_flash_sales
"""
from alembic import op
import sqlalchemy as sa


revision = "057_customer_auth_and_whatsapp_orders"
down_revision = "056_create_flash_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for required in ("user_details", "online_customers"):
        if required not in tables:
            raise RuntimeError(
                f"{required} is missing; refusing to provision dependent tables"
            )

    enum_names = {
        item["name"] for item in sa.inspect(bind).get_enums(schema="public")
    }
    if "whatsapp_order_status" not in enum_names:
        whatsapp_status = sa.Enum(
            "PENDING",
            "ACCEPTED",
            "COMPLETED",
            "REJECTED",
            name="whatsapp_order_status",
        )
        whatsapp_status.create(bind, checkfirst=True)

    if "whatsapp_orders" not in tables:
        op.create_table(
            "whatsapp_orders",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "shop_id",
                sa.Integer(),
                sa.ForeignKey("user_details.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sender_number", sa.String(length=20), nullable=True),
            sa.Column("raw_text", sa.Text(), nullable=False),
            sa.Column("parsed_items_json", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Enum(
                    "PENDING",
                    "ACCEPTED",
                    "COMPLETED",
                    "REJECTED",
                    name="whatsapp_order_status",
                    create_type=False,
                ),
                nullable=True,
                server_default="PENDING",
            ),
            sa.Column(
                "total_amount",
                sa.Numeric(precision=10, scale=2),
                nullable=True,
                server_default="0.00",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )

    if "customer_password_resets" not in tables:
        op.create_table(
            "customer_password_resets",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "customer_id",
                sa.Integer(),
                sa.ForeignKey("online_customers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(length=128), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "used",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )

    if "customer_password_reset_otps" not in tables:
        op.create_table(
            "customer_password_reset_otps",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "customer_id",
                sa.Integer(),
                sa.ForeignKey("online_customers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("otp_hash", sa.String(length=128), nullable=False),
            sa.Column("otp_expires_at", sa.DateTime(), nullable=False),
            sa.Column(
                "otp_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("reset_token_hash", sa.String(length=128), nullable=True),
            sa.Column("reset_token_expires_at", sa.DateTime(), nullable=True),
            sa.Column(
                "used",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        )

    # Match the indexes declared by the SQLAlchemy models.
    for table_name, index_name in (
        ("customer_password_resets", "ix_customer_password_resets_customer_id"),
        ("customer_password_resets", "ix_customer_password_resets_expires_at"),
        ("customer_password_resets", "ix_customer_password_resets_used"),
        ("customer_password_reset_otps", "ix_customer_password_reset_otps_customer_id"),
        ("customer_password_reset_otps", "ix_customer_password_reset_otps_otp_expires_at"),
        ("customer_password_reset_otps", "ix_customer_password_reset_otps_used"),
    ):
        existing = {
            item["name"]
            for item in sa.inspect(bind).get_indexes(table_name)
        }
        if index_name not in existing:
            column_name = index_name.removeprefix(f"ix_{table_name}_")
            op.create_index(index_name, table_name, [column_name], unique=False)

    for table_name, index_name, column_name in (
        (
            "customer_password_resets",
            "ix_customer_password_resets_token_hash",
            "token_hash",
        ),
        (
            "customer_password_reset_otps",
            "ix_customer_password_reset_otps_reset_token_hash",
            "reset_token_hash",
        ),
    ):
        existing = {
            item["name"]
            for item in sa.inspect(bind).get_indexes(table_name)
        }
        if index_name not in existing:
            op.create_index(index_name, table_name, [column_name], unique=True)


def downgrade() -> None:
    # Retain authentication and order records on rollback.
    pass
