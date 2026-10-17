"""Repair legacy password reset columns and add bounded OTP attempts.

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

    columns = {
        column["name"]: column
        for column in inspector.get_columns("password_resets")
    }

    # Some deployments still have the original reset-token schema
    # (reset_token/token_expiry/is_used) instead of the newer
    # (token_hash/expires_at) fields expected by the current ORM. Add the
    # current columns in-place and make any retained legacy-only required
    # columns nullable, so current ORM inserts do not violate old constraints.
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
        (
            "token_hash",
            sa.Column(
                "token_hash",
                sa.String(length=128),
                nullable=False,
                server_default="legacy-disabled",
            ),
        ),
        (
            "expires_at",
            sa.Column(
                "expires_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("'1970-01-01 00:00:00'"),
            ),
        ),
    ]

    for name, column in repairs:
        if name not in columns:
            op.add_column("password_resets", column)
            columns[name] = {"name": name, "type": column.type, "nullable": column.nullable}

    # Preserve old expiration timestamps when present. Old rows without an
    # expiration mapping remain expired at the safe epoch default.
    if "token_expiry" in columns and "expires_at" in columns:
        op.execute(
            sa.text(
                "UPDATE password_resets "
                "SET expires_at = token_expiry "
                "WHERE token_expiry IS NOT NULL AND expires_at = '1970-01-01 00:00:00'"
            )
        )

    legacy_required = [
        name
        for name in ("reset_token", "token_expiry")
        if name in columns and not columns[name].get("nullable", True)
    ]
    if legacy_required:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("password_resets") as batch_op:
                for name in legacy_required:
                    batch_op.alter_column(
                        name,
                        existing_type=columns[name]["type"],
                        existing_nullable=False,
                        nullable=True,
                    )
        else:
            for name in legacy_required:
                op.alter_column(
                    "password_resets",
                    name,
                    existing_type=columns[name]["type"],
                    existing_nullable=False,
                    nullable=True,
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "password_resets" not in set(inspector.get_table_names()):
        return

    # Only attempts belongs uniquely to this revision. Leave schema-repair
    # columns and relaxed legacy constraints in place to avoid deleting data.
    columns = {column["name"] for column in inspector.get_columns("password_resets")}
    if "attempts" in columns:
        op.drop_column("password_resets", "attempts")
