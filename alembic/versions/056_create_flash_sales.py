"""Create the flash-sales table used by invoice pricing and online-store discounts.

Revision ID: 056_create_flash_sales
Revises: 055_khata_name_only_accounts
"""
from alembic import op
import sqlalchemy as sa


revision = "056_create_flash_sales"
down_revision = "055_khata_name_only_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "user_details" not in tables:
        raise RuntimeError(
            "user_details is missing; refusing to create flash_sales without its owner table"
        )

    if "flash_sales" not in tables:
        op.create_table(
            "flash_sales",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("user_details.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("discount_pct", sa.Float(), nullable=False),
            sa.Column("hours_duration", sa.Integer(), nullable=False),
            sa.Column(
                "start_time",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
            sa.Column("end_time", sa.DateTime(), nullable=False),
            sa.Column(
                "is_active",
                sa.Boolean(),
                nullable=True,
                server_default=sa.true(),
            ),
        )

    # Repair the index if a partially provisioned database already has the table.
    indexes = {
        item["name"]: item
        for item in sa.inspect(bind).get_indexes("flash_sales")
    }
    index_name = "ix_flash_sales_user_id"
    if index_name not in indexes:
        op.create_index(index_name, "flash_sales", ["user_id"], unique=False)

    # Fail early on a pre-existing but incomplete table instead of allowing
    # invoice synchronization to fail later at request time.
    columns = {
        item["name"]
        for item in sa.inspect(bind).get_columns("flash_sales")
    }
    required_columns = {
        "id",
        "user_id",
        "category",
        "discount_pct",
        "hours_duration",
        "start_time",
        "end_time",
        "is_active",
    }
    missing = sorted(required_columns - columns)
    if missing:
        raise RuntimeError(
            "flash_sales exists but is missing required columns: "
            + ", ".join(missing)
        )


def downgrade() -> None:
    # Flash-sale data is operational business data; retain it on rollback.
    pass
