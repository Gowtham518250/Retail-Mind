"""Add the missing payment idempotency key expected by the ORM.

Revision ID: 039_payment_idempotency_key
Revises: 038_legacy_startup_schema_repairs

The column is nullable so existing payment rows remain valid and unchanged.
A unique index enforces replay protection for non-NULL keys; PostgreSQL permits
multiple NULL values in a normal unique index.
"""
from alembic import op
import sqlalchemy as sa

revision = "039_payment_idempotency_key"
down_revision = "038_legacy_startup_schema_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "payments" not in tables:
        raise RuntimeError(
            "payments table is missing; refusing to apply payment idempotency migration"
        )

    columns = {column["name"] for column in inspector.get_columns("payments")}
    if "idempotency_key" not in columns:
        op.add_column(
            "payments",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )

    # Re-inspect after the possible column addition. The migration is safe to
    # retry on deployments where the column/index was manually repaired already.
    indexes = {
        index["name"]: index for index in sa.inspect(bind).get_indexes("payments")
    }
    index_name = "ix_payments_idempotency_key"
    if index_name not in indexes:
        current_columns = {
            column["name"] for column in sa.inspect(bind).get_columns("payments")
        }
        if "idempotency_key" in current_columns:
            op.create_index(
                index_name,
                "payments",
                ["idempotency_key"],
                unique=True,
            )


def downgrade() -> None:
    # Deliberately retain the column and unique index. Removing this key during
    # downgrade could erase replay-protection data written after the migration.
    pass
