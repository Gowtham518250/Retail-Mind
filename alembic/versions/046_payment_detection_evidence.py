"""Persist owner-device payment detection evidence without settling invoices.

Revision ID: 046_payment_detection_evidence
Revises: 045_fractional_min_stock_product_create_idempotency
"""
from alembic import op
import sqlalchemy as sa

revision = "046_payment_detection_evidence"
down_revision = "045_fractional_min_stock_product_create_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "payment_detection_events" not in tables:
        op.create_table(
            "payment_detection_events",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("shop_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("event_key", sa.String(length=128), nullable=False),
            sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True),
            sa.Column("amount", sa.Numeric(10, 2), nullable=False),
            sa.Column("direction", sa.String(length=16), nullable=False, server_default="unknown"),
            sa.Column("payer_name", sa.String(length=120), nullable=True),
            sa.Column("payer_phone", sa.String(length=20), nullable=True),
            sa.Column("payer_vpa", sa.String(length=100), nullable=True),
            sa.Column("bank_name", sa.String(length=80), nullable=True),
            sa.Column("account_suffix", sa.String(length=4), nullable=True),
            sa.Column("reference_id", sa.String(length=100), nullable=True),
            sa.Column("detected_source", sa.String(length=80), nullable=False),
            sa.Column("payment_app", sa.String(length=40), nullable=True),
            sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False, server_default="0"),
            sa.Column("decision", sa.String(length=16), nullable=False, server_default="likely"),
            sa.Column("verification_status", sa.String(length=24), nullable=False, server_default="unverified"),
            sa.Column("source_event_hash", sa.String(length=64), nullable=True),
            sa.Column("detected_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("shop_id", "event_key", name="uq_payment_detection_shop_event"),
        )
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("payment_detection_events")}
    if "payment_detection_events" in set(inspector.get_table_names()):
        indexes = {i["name"] for i in inspector.get_indexes("payment_detection_events")}
        specs = (
            ("ix_payment_detection_shop_detected", ["shop_id", "detected_at"]),
            ("ix_payment_detection_shop_reference", ["shop_id", "reference_id"]),
            ("ix_payment_detection_shop_decision", ["shop_id", "decision"]),
        )
        for name, cols in specs:
            if name not in indexes and all(col in columns for col in cols):
                op.create_index(name, "payment_detection_events", cols, unique=False)


def downgrade() -> None:
    # Keep financial audit evidence on downgrade.
    pass
