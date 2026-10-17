""""Repair legacy password reset columns and add bounded OTP attempts.

Revision ID: 037_password_reset_attempts
Revises: 036_email_otp_challenges
"""
from alembic import op
import sqlalchemy as sa

revision = "037_password_reset_attempts"
down_revision = "036_email_otp_challenges"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "password_resets" not in tables:
        raise RuntimeError(
            "password_resets table is missing; refusing to apply OTP security migration"
        )

    columns = {column["name"] for column in inspector.get_columns("password_resets")}

    # Some deployed schemas predate fields used by the owner OTP flow. Reconcile
    # those columns in-place before enforcing attempt tracking. These additions
    # are nullable/defaulted so existing password-reset data remains intact.
    repairs = [
        (
            "reference_id",
            sa.Column("reference_id", sa.String(length=100), nullable=True),
        ),
        (
            "description",
            sa.Column("description", sa.String(length=200), nullable=True),
        ),
        (
            "transaction_date",
            sa.Column(
                "transaction_date",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        ),
        (
            "attempts",
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        ),
        (
            "created_at",
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=True,
                server_default=sa.func.now(),
            ),
        ),
    ]

    for name, column in repairs:
        if name not in columns:
            op.add_column("password_resets", column)
            columns.add(name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "password_resets" not in set(inspector.get_table_names()):
        return

    # Only attempts belongs uniquely to this revision. The nullable legacy
    # columns above are schema-repair additions and may have existed in an older
    # deployment; leave them in place on downgrade to avoid deleting data.
    columns = {column["name"] for column in inspector.get_columns("password_resets")}
    if "attempts" in columns:
        op.drop_column("password_resets", "attempts")
