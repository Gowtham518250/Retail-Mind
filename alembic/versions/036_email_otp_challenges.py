"""Add shared, attempt-limited email OTP challenges.

Revision ID: 036_email_otp_challenges
Revises: 035_ensure_online_customers_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "036_email_otp_challenges"
down_revision = "035_ensure_online_customers_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "email_otp_challenges" not in tables:
        op.create_table(
            "email_otp_challenges",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("purpose", sa.String(length=64), nullable=False, server_default="Verification"),
            sa.Column("otp_hash", sa.String(length=64), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("email_otp_challenges")}
    if "ix_email_otp_challenges_email" not in indexes:
        op.create_index(
            "ix_email_otp_challenges_email",
            "email_otp_challenges",
            ["email"],
            unique=False,
        )
    if "ix_email_otp_challenges_purpose" not in indexes:
        op.create_index(
            "ix_email_otp_challenges_purpose",
            "email_otp_challenges",
            ["purpose"],
            unique=False,
        )
    if "ix_email_otp_challenges_expires_at" not in indexes:
        op.create_index(
            "ix_email_otp_challenges_expires_at",
            "email_otp_challenges",
            ["expires_at"],
            unique=False,
        )
    if "ix_email_otp_email_purpose_created" not in indexes:
        op.create_index(
            "ix_email_otp_email_purpose_created",
            "email_otp_challenges",
            ["email", "purpose", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "email_otp_challenges" not in tables:
        return

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("email_otp_challenges")}
    for index_name in (
        "ix_email_otp_email_purpose_created",
        "ix_email_otp_challenges_expires_at",
        "ix_email_otp_challenges_purpose",
        "ix_email_otp_challenges_email",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="email_otp_challenges")
    op.drop_table("email_otp_challenges")
