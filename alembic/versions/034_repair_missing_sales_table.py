"""Repair a missing sales table in an adopted or partially initialized database.

Revision ID: 034_repair_missing_sales_table
Revises: 033_add_payment_confirmation_source

The initial schema creates sales, but legacy-schema adoption can mark the
initial revision as applied when only user_details exists. Earlier sales
reference migrations intentionally skipped when the table was absent. This
forward migration restores the table and expected indexes without replacing
an existing sales table or deleting rows.
"""
from alembic import op
import sqlalchemy as sa

revision = "034_repair_missing_sales_table"
down_revision = "033_add_payment_confirmation_source"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "sales" not in tables:
        if "user_details" not in tables:
            raise RuntimeError(
                "Cannot repair missing sales table: user_details is also missing. "
                "Verify DATABASE_URL and repair the baseline schema before starting."
            )

        op.create_table(
            "sales",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("shopkeeper_id", sa.Integer(), nullable=False),
            sa.Column("product_name", sa.String(length=100), nullable=False),
            sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("total", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("sale_date", sa.Date(), nullable=True),
            sa.Column("reference_order_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["shopkeeper_id"],
                ["user_details.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    # Refresh inspection after creating the table, then add the order-reference
    # column in case sales existed in an older schema.
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("sales")}
    if "reference_order_id" not in columns:
        op.add_column(
            "sales",
            sa.Column("reference_order_id", sa.Integer(), nullable=True),
        )

    # Safe both for newly created tables and tables that already have some
    # of these indexes. No existing sales records are modified or removed.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_shopkeeper_id ON sales (shopkeeper_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_sale_date ON sales (sale_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sales_reference_order_id "
        "ON sales (reference_order_id)"
    )


def downgrade() -> None:
    # Intentionally preserve the table and data. This is a repair migration
    # for deployments where sales may have existed before this revision.
    pass
