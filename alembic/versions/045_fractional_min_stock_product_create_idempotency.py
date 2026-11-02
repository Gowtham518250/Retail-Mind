"""Store fractional reorder thresholds and product-create idempotency keys.

Revision ID: 045_fractional_min_stock_product_create_idempotency
Revises: 044_upi_reservation_expiry_index
"""
from alembic import op
import sqlalchemy as sa


revision = "045_fractional_min_stock_product_create_idempotency"
down_revision = "044_upi_reservation_expiry_index"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "products" not in inspector.get_table_names():
        raise RuntimeError("Required products table is missing; refusing product identity migration.")

    product_columns = {column["name"]: column for column in inspector.get_columns("products")}
    if "min_stock" not in product_columns:
        raise RuntimeError("Required products.min_stock column is missing.")

    current_type = product_columns["min_stock"]["type"]
    if not (
        isinstance(current_type, sa.Numeric)
        and getattr(current_type, "precision", None) == 12
        and getattr(current_type, "scale", None) == 3
    ):
        op.alter_column(
            "products",
            "min_stock",
            existing_type=current_type,
            type_=sa.Numeric(12, 3),
            existing_nullable=product_columns["min_stock"].get("nullable", True),
            postgresql_using="min_stock::numeric(12, 3)",
        )

    if "product_create_requests" not in inspector.get_table_names():
        op.create_table(
            "product_create_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("user_details.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("operation_id", sa.String(length=128), nullable=False),
            sa.Column(
                "product_id",
                sa.Integer(),
                sa.ForeignKey("products.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint(
                "user_id",
                "operation_id",
                name="uq_product_create_user_operation",
            ),
        )
        op.create_index("ix_product_create_requests_user_id", "product_create_requests", ["user_id"])
        op.create_index("ix_product_create_requests_product_id", "product_create_requests", ["product_id"])


def downgrade():
    # Keep NUMERIC(12, 3): converting reorder thresholds back to INTEGER could
    # silently destroy fractional thresholds already saved by production shops.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "product_create_requests" in inspector.get_table_names():
        op.drop_index("ix_product_create_requests_product_id", table_name="product_create_requests")
        op.drop_index("ix_product_create_requests_user_id", table_name="product_create_requests")
        op.drop_table("product_create_requests")
