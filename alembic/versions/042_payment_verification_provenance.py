"""Add payment verification provenance.

Revision ID: 042_payment_verification_provenance
Revises: 041_cancelled_online_order_financial_cleanup

Existing payment rows are marked legacy/unknown rather than retroactively
claiming they were verified. New API writes must set a supported verification
status explicitly before invoice balances can be changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "042_payment_verification_provenance"
down_revision = "041_cancelled_online_order_financial_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "payments" not in tables:
        raise RuntimeError(
            "payments table is missing; refusing to apply verification migration"
        )

    columns = {column["name"] for column in inspector.get_columns("payments")}
    if "verification_status" not in columns:
        op.add_column(
            "payments",
            sa.Column(
                "verification_status",
                sa.String(length=30),
                nullable=False,
                server_default="LEGACY_UNVERIFIED",
            ),
        )

    columns = {column["name"] for column in sa.inspect(bind).get_columns("payments")}
    if "verification_method" not in columns:
        op.add_column(
            "payments",
            sa.Column(
                "verification_method",
                sa.String(length=30),
                nullable=False,
                server_default="LEGACY_UNKNOWN",
            ),
        )

    columns = {column["name"] for column in sa.inspect(bind).get_columns("payments")}
    if "verification_actor_id" not in columns:
        op.add_column(
            "payments",
            sa.Column("verification_actor_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    # Keep provenance fields during downgrade: dropping them would erase audit
    # context and could misrepresent historical payments as verified.
    pass
