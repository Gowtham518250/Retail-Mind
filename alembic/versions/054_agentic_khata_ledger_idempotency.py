"""Add replay protection for owner-confirmed agent Khata ledger movements.

Revision ID: 054_agentic_khata_ledger_idempotency
Revises: 053_agentic_assistant
"""
from alembic import op
import sqlalchemy as sa

revision = "054_agentic_khata_ledger_idempotency"
down_revision = "053_agentic_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "khata_history" not in tables:
        raise RuntimeError("khata_history is missing; refusing to add agent replay protection")

    columns = {column["name"] for column in inspector.get_columns("khata_history")}
    if "idempotency_key" not in columns:
        op.add_column(
            "khata_history",
            sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        )

    indexes = {
        item["name"]: item
        for item in sa.inspect(bind).get_indexes("khata_history")
    }
    index_name = "uq_khata_history_idempotency_key"
    existing = indexes.get(index_name)
    if existing is not None and not existing.get("unique", False):
        op.drop_index(index_name, table_name="khata_history")
        existing = None
    if existing is None:
        op.create_index(
            index_name,
            "khata_history",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    # Retain replay protection for financial records created after this revision.
    pass
