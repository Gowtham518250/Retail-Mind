"""Allow fractional invoice line quantities.

Revision ID: 006_frac_qty
Revises: 005_add_worker_id_to_attendance
"""
from alembic import op
import sqlalchemy as sa

revision = "006_frac_qty"
down_revision = "005_add_worker_id_to_attendance"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column = next(
        column for column in inspector.get_columns("invoice_line_items")
        if column["name"] == "quantity"
    )
    column_type = column["type"]

    already_fractional = (
        isinstance(column_type, sa.Numeric)
        and getattr(column_type, "precision", None) == 12
        and getattr(column_type, "scale", None) == 3
    )

    if not already_fractional:
        op.alter_column(
            "invoice_line_items",
            "quantity",
            existing_type=column_type,
            type_=sa.Numeric(12, 3),
            existing_nullable=False,
        )


def downgrade():
    op.alter_column(
        "invoice_line_items",
        "quantity",
        existing_type=sa.Numeric(12, 3),
        type_=sa.Integer(),
        existing_nullable=False,
    )
