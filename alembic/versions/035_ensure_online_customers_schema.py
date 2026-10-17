"""Ensure the separate online-customer account table exists.

Revision ID: 035_ensure_online_customers_schema
Revises: 034_repair_missing_sales_table
"""
from alembic import op
import sqlalchemy as sa

revision = "035_ensure_online_customers_schema"
down_revision = "034_repair_missing_sales_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "online_customers" not in tables:
        op.create_table(
            "online_customers",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_name", sa.String(length=100), nullable=False),
            sa.Column("email", sa.String(length=100), nullable=True),
            sa.Column("phone", sa.String(length=20), nullable=True),
            sa.Column("city", sa.String(length=100), nullable=True),
            sa.Column("address", sa.Text(), nullable=True),
            sa.Column("password", sa.String(length=100), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.UniqueConstraint("email", name="uq_online_customers_email"),
        )
        op.create_index(
            "ix_online_customers_phone",
            "online_customers",
            ["phone"],
            unique=True,
        )
        return

    # Existing production databases may have an older form of this table.
    # Add the optional delivery/location fields without replacing customer rows.
    columns = {column["name"]: column for column in inspector.get_columns("online_customers")}
    if "email" in columns and not columns["email"]["nullable"]:
        op.alter_column("online_customers", "email", existing_type=sa.String(length=100), nullable=True)

    optional_columns = {
        "phone": sa.String(length=20),
        "city": sa.String(length=100),
        "address": sa.Text(),
    }
    for name, column_type in optional_columns.items():
        if name not in columns:
            op.add_column(
                "online_customers",
                sa.Column(name, column_type, nullable=True),
            )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("online_customers")}
    if "ix_online_customers_phone" not in indexes:
        op.create_index(
            "ix_online_customers_phone",
            "online_customers",
            ["phone"],
            unique=True,
        )


def downgrade() -> None:
    # Keep customer accounts and their authentication data on downgrade.
    pass
