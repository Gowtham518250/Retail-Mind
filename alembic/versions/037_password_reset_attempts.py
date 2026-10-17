"""Add bounded attempt tracking to password reset challenges.

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
        raise RuntimeError("password_resets table is missing; refusing to apply OTP security migration")

    columns = {column["name"] for column in inspector.get_columns("password_resets")}
    if "attempts" not in columns:
        op.add_column(
            "password_resets",
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "password_resets" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("password_resets")}
    if "attempts" in columns:
        op.drop_column("password_resets", "attempts")
