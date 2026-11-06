"""Persist shop-specific speech corrections for voice billing.

An alias becomes active only after repeated cashier-confirmed corrections. The
alias is scoped to one shop and one language and always points to a real catalog
product. It never stores or grants a price, size, stock quantity, or invoice action.
"""
from alembic import op
import sqlalchemy as sa


revision = "050_product_voice_aliases"
down_revision = "049_growth_marketing_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_voice_aliases" not in tables:
        op.create_table(
            "product_voice_aliases",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("product_id", sa.Integer(), nullable=False),
            sa.Column("alias_text", sa.String(length=80), nullable=False),
            sa.Column("normalized_alias", sa.String(length=120), nullable=False),
            sa.Column("language_code", sa.String(length=16), nullable=False, server_default="en"),
            sa.Column("confirmation_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["user_id"], ["user_details.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
            sa.UniqueConstraint(
                "user_id",
                "language_code",
                "normalized_alias",
                name="uq_product_voice_alias_shop_language_phrase",
            ),
        )

    inspector = sa.inspect(bind)
    if "product_voice_aliases" not in set(inspector.get_table_names()):
        raise RuntimeError("product_voice_aliases table was not created")

    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("product_voice_aliases")
    }
    indexes = {
        index["name"]
        for index in sa.inspect(bind).get_indexes("product_voice_aliases")
    }
    index_specs = (
        ("ix_product_voice_aliases_user_id", ["user_id"]),
        ("ix_product_voice_aliases_product_id", ["product_id"]),
        ("ix_product_voice_alias_shop_language_active", ["user_id", "language_code", "is_active"]),
    )
    for name, column_names in index_specs:
        if name not in indexes and all(column in columns for column in column_names):
            op.create_index(name, "product_voice_aliases", column_names, unique=False)


def downgrade() -> None:
    # Keep cashier-confirmed aliases for reliable voice billing history.
    pass
