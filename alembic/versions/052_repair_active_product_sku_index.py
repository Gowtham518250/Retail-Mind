"""Repair active-only shop/SKU uniqueness for databases with legacy indexes.

Revision ID: 052_repair_active_product_sku_index
Revises: 051_active_product_sku_and_poster_svg
"""
from alembic import op
import sqlalchemy as sa

revision = "052_repair_active_product_sku_index"
down_revision = "051_active_product_sku_and_poster_svg"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_products_active_shop_sku"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "products" not in inspector.get_table_names():
        return

    # Remove legacy uniqueness regardless of the historical constraint/index
    # name. Keep ordinary lookup indexes and the intended partial index.
    for constraint in inspector.get_unique_constraints("products"):
        columns = tuple(constraint.get("column_names") or ())
        if set(columns) == {"user_id", "sku"}:
            name = constraint.get("name")
            if name:
                op.drop_constraint(name, "products", type_="unique")

    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("products"):
        columns = tuple(index.get("column_names") or ())
        if index.get("unique") and set(columns) == {"user_id", "sku"} and index.get("name") != INDEX_NAME:
            op.drop_index(index["name"], table_name="products")

    inspector = sa.inspect(bind)
    indexes = {item["name"]: item for item in inspector.get_indexes("products")}
    expected = indexes.get(INDEX_NAME)
    if expected and not expected.get("unique"):
        op.drop_index(INDEX_NAME, table_name="products")
        expected = None
    if expected is None:
        op.create_index(
            INDEX_NAME,
            "products",
            ["user_id", "sku"],
            unique=True,
            postgresql_where=sa.text("is_active IS TRUE"),
            sqlite_where=sa.text("is_active = 1"),
        )


def downgrade() -> None:
    # Keep the safe partial unique index: restoring all-row uniqueness would
    # make legitimate re-creation of archived products fail again.
    pass
