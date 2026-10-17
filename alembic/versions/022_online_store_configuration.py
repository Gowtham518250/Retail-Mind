"""Persist online-store configuration per shop.

Revision ID: 022_online_store_configuration
Revises: 021_online_order_lifecycle_reviews
Create Date: 2026-10-04

The online_setup_fee column was introduced in revision 016. This revision
must not add it again; the remaining configuration columns are added only
when absent so fresh and partially-upgraded schemas are both supported.
"""

from alembic import op
import sqlalchemy as sa


revision = "022_online_store_configuration"
down_revision = "021_online_order_lifecycle_reviews"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("online_min_order", sa.Numeric(10, 2), "0"),
    ("online_delivery_fee", sa.Numeric(10, 2), "0"),
    ("online_offer_delivery", sa.Boolean(), sa.true()),
    ("online_offer_pickup", sa.Boolean(), sa.true()),
    ("online_accept_cod", sa.Boolean(), sa.true()),
    ("online_accept_online", sa.Boolean(), sa.false()),
)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "shop_profiles" not in tables:
        raise RuntimeError(
            "Cannot configure online store: shop_profiles table is missing. "
            "Verify the baseline schema before applying migration 022."
        )

    existing_columns = {
        column["name"] for column in inspector.get_columns("shop_profiles")
    }
    for name, column_type, default in _COLUMNS:
        if name not in existing_columns:
            op.add_column(
                "shop_profiles",
                sa.Column(
                    name,
                    column_type,
                    nullable=False,
                    server_default=default,
                ),
            )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "shop_profiles" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("shop_profiles")
    }
    for name, _column_type, _default in reversed(_COLUMNS):
        if name in existing_columns:
            op.drop_column("shop_profiles", name)
