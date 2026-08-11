"""Allow fractional invoice line quantities.

Revision ID: 006_allow_fractional_invoice_quantities
Revises: 005_add_worker_id_to_attendance
"""
from alembic import op
import sqlalchemy as sa

revision = "006_allow_fractional_invoice_quantities"
down_revision = "005_add_worker_id_to_attendance"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "invoice_line_items",
        "quantity",
        existing_type=sa.Integer(),
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
