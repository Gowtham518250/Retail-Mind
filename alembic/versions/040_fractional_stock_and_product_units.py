"""Support fractional stock quantities and explicit product units.

Revision ID: 040_fractional_stock_units
Revises: 039_payment_idempotency_key

Product stock, stock movements, and batch quantities are stored to 3 decimal
places. Product units are persisted so quantities such as 0.500 kg are not
ambiguous when displayed or synchronized between devices.
"""
from alembic import op
import sqlalchemy as sa


revision = "040_fractional_stock_units"
down_revision = "039_payment_idempotency_key"
branch_labels = None
depends_on = None


def _column(bind, table_name: str, column_name: str):
    inspector = sa.inspect(bind)
    if table_name not in inspector.get_table_names():
        raise RuntimeError(f"Required table is missing: {table_name}")
    for column in inspector.get_columns(table_name):
        if column["name"] == column_name:
            return column
    raise RuntimeError(f"Required column is missing: {table_name}.{column_name}")


def _ensure_fractional_column(bind, table_name: str, column_name: str) -> None:
    column = _column(bind, table_name, column_name)
    current_type = column["type"]
    already_fractional = (
        isinstance(current_type, sa.Numeric)
        and getattr(current_type, "precision", None) == 12
        and getattr(current_type, "scale", None) == 3
    )
    if not already_fractional:
        op.alter_column(
            table_name,
            column_name,
            existing_type=current_type,
            type_=sa.Numeric(12, 3),
            existing_nullable=column.get("nullable", True),
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "products" not in tables:
        raise RuntimeError("Required products table is missing; refusing stock-unit migration")

    product_columns = {column["name"] for column in inspector.get_columns("products")}
    if "unit" not in product_columns:
        op.add_column(
            "products",
            sa.Column(
                "unit",
                sa.String(length=20),
                nullable=False,
                server_default="pcs",
            ),
        )

    # Existing integer stock values convert losslessly to NUMERIC(12, 3).
    _ensure_fractional_column(bind, "products", "current_stock")
    _ensure_fractional_column(bind, "stock_movements", "quantity")
    _ensure_fractional_column(bind, "product_batches", "quantity")


def downgrade() -> None:
    # Intentionally retain decimal stock and unit data. Converting fractional
    # quantities back to integers would silently discard inventory.
    pass
