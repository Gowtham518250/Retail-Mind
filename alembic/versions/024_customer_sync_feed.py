"""Add customer-scoped ordered sync feed for order-history recovery.

Revision ID: 024_customer_sync_feed
Revises: 023_durable_sync_outbox
"""
from alembic import op
import sqlalchemy as sa


revision = "024_customer_sync_feed"
down_revision = "023_durable_sync_outbox"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "customer_sync_clocks",
        sa.Column("customer_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("seq", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.create_table(
        "customer_sync_events",
        sa.Column("customer_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("seq", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("event_id", name="uq_customer_sync_events_event_id"),
    )
    op.create_index(
        "ix_customer_sync_events_customer_type_seq",
        "customer_sync_events",
        ["customer_id", "event_type", "seq"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_customer_sync_events_customer_type_seq",
        table_name="customer_sync_events",
    )
    op.drop_table("customer_sync_events")
    op.drop_table("customer_sync_clocks")
