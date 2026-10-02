"""Backfill legacy shop active flags for marketplace visibility.

Revision ID: 018_repair_shop_active_flags
Revises: 017_repair_marketplace_schema
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "018_repair_shop_active_flags"
down_revision = "017_repair_marketplace_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "shop_profiles" in tables:
        columns = {column["name"] for column in inspector.get_columns("shop_profiles")}
        if "is_active" in columns:
            # Existing production rows may predate the current model default.
            # A null flag means "not explicitly disabled", so preserve them as active.
            bind.execute(
                sa.text(
                    "UPDATE shop_profiles "
                    "SET is_active = TRUE "
                    "WHERE is_active IS NULL"
                )
            )


def downgrade() -> None:
    # Backfill-only migration; do not undo existing shop activation state.
    pass
