"""Add durable per-shop synchronization change log.

Revision ID: 023_durable_sync_outbox
Revises: 022_online_store_configuration
"""
from alembic import op
import sqlalchemy as sa


revision = "023_durable_sync_outbox"
down_revision = "022_online_store_configuration"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sync_clocks",
        sa.Column("shop_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "sync_events",
        sa.Column("shop_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("seq", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", name="uq_sync_events_event_id"),
    )
    op.create_index(
        "ix_sync_events_shop_type_seq",
        "sync_events",
        ["shop_id", "event_type", "seq"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_sync_events_shop_type_seq", table_name="sync_events")
    op.drop_table("sync_events")
    op.drop_table("sync_clocks")
