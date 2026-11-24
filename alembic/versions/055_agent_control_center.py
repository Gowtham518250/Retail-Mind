"""Add per-shop AI agent preferences and subscription entitlements.

Revision ID: 055_agent_control_center
Revises: 054_agentic_khata_ledger_idempotency
"""
from alembic import op
import sqlalchemy as sa
import json

revision = "055_agent_control_center"
down_revision = "054_agentic_khata_ledger_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "rm_shop_agent_settings" not in tables:
        op.create_table(
            "rm_shop_agent_settings",
            sa.Column(
                "shop_id",
                sa.Integer(),
                sa.ForeignKey("user_details.id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "assistant_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "voice_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "actions_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # Daily limits already exist: BASIC 7, PRO 25 and BUSINESS 75 queries.
    # This migration adds independent feature codes without overwriting any
    # existing plan entitlements.
    plan_entitlements = {
        "FREE": {
            "ai_agent": False,
            "ai_agent_voice": False,
            "ai_agent_actions": False,
        },
        "BASIC": {
            "ai_agent": True,
            "ai_agent_voice": False,
            "ai_agent_actions": False,
        },
        "PRO": {
            "ai_agent": True,
            "ai_agent_voice": True,
            "ai_agent_actions": False,
        },
        "BUSINESS": {
            "ai_agent": True,
            "ai_agent_voice": True,
            "ai_agent_actions": True,
        },
    }
    if "rm_subscription_plans" in tables:
        for plan_code, entitlements in plan_entitlements.items():
            bind.execute(
                sa.text("""
                    UPDATE rm_subscription_plans
                    SET features = COALESCE(features, '{}'::jsonb) || CAST(:features AS jsonb)
                    WHERE plan_code = :plan_code
                """),
                {
                    "plan_code": plan_code,
                    "features": json.dumps(entitlements),
                },
            )


def downgrade() -> None:
    # Keep owner preferences and applied subscription entitlements so rollback
    # cannot unexpectedly re-enable previously disabled assistant settings.
    pass
