"""Allow barcode reuse after product archival and store generated poster assets."""
from alembic import op
import sqlalchemy as sa

revision = "051_active_product_sku_and_poster_svg"
down_revision = "050_product_voice_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "products" in tables:
        unique_constraints = {
            item.get("name")
            for item in sa.inspect(bind).get_unique_constraints("products")
        }
        if "uix_user_sku" in unique_constraints:
            if bind.dialect.name == "sqlite":
                with op.batch_alter_table("products") as batch:
                    batch.drop_constraint("uix_user_sku", type_="unique")
            else:
                op.drop_constraint("uix_user_sku", "products", type_="unique")

        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("products")}
        if "uq_products_active_shop_sku" not in indexes:
            op.create_index(
                "uq_products_active_shop_sku",
                "products",
                ["user_id", "sku"],
                unique=True,
                postgresql_where=sa.text("is_active IS TRUE"),
                sqlite_where=sa.text("is_active = 1"),
            )

    if "growth_marketing_campaigns" in tables:
        columns = {
            item["name"]
            for item in sa.inspect(bind).get_columns("growth_marketing_campaigns")
        }
        if "poster_svg" not in columns:
            op.add_column(
                "growth_marketing_campaigns",
                sa.Column("poster_svg", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "products" in tables:
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("products")}
        if "uq_products_active_shop_sku" in indexes:
            op.drop_index("uq_products_active_shop_sku", table_name="products")
        # Do not restore the former all-rows unique constraint: archived and
        # replacement products may legitimately share a barcode after upgrade.

    if "growth_marketing_campaigns" in tables:
        columns = {
            item["name"]
            for item in sa.inspect(bind).get_columns("growth_marketing_campaigns")
        }
        if "poster_svg" in columns:
            op.drop_column("growth_marketing_campaigns", "poster_svg")
