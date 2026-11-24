"""Persist Retail Mind agent conversations, confirmations and tool audit records."""
from alembic import op
import sqlalchemy as sa


revision = "051_agentic_assistant"
down_revision = "050_product_voice_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "agent_conversations" not in tables:
        op.create_table(
            "agent_conversations",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False, server_default="New assistant conversation"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "agent_messages" not in tables:
        op.create_table(
            "agent_messages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "agent_pending_actions" not in tables:
        op.create_table(
            "agent_pending_actions",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False),
            sa.Column("action_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
            sa.Column("idempotency_key", sa.String(length=128), nullable=False),
            sa.Column("preview", sa.JSON(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("preview_hash", sa.String(length=64), nullable=False),
            sa.Column("invoice_number", sa.String(length=64), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("result", sa.JSON(), nullable=True),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_agent_action_user_idempotency"),
        )

    if "agent_tool_executions" not in tables:
        op.create_table(
            "agent_tool_executions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("user_details.id", ondelete="CASCADE"), nullable=False),
            sa.Column("conversation_id", sa.String(length=36), sa.ForeignKey("agent_conversations.id", ondelete="SET NULL"), nullable=True),
            sa.Column("request_id", sa.String(length=36), nullable=False),
            sa.Column("tool_name", sa.String(length=80), nullable=False),
            sa.Column("success", sa.Boolean(), nullable=False),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    inspector = sa.inspect(bind)
    index_specs = {
        "agent_conversations": [
            ("ix_agent_conversations_user_updated", ["user_id", "updated_at"]),
            ("ix_agent_conversations_user_id", ["user_id"]),
        ],
        "agent_messages": [
            ("ix_agent_messages_conversation_created", ["conversation_id", "created_at", "id"]),
            ("ix_agent_messages_conversation_id", ["conversation_id"]),
            ("ix_agent_messages_user_id", ["user_id"]),
        ],
        "agent_pending_actions": [
            ("ix_agent_pending_actions_user_status", ["user_id", "status"]),
            ("ix_agent_pending_actions_expiry", ["status", "expires_at"]),
            ("ix_agent_pending_actions_user_id", ["user_id"]),
            ("ix_agent_pending_actions_conversation_id", ["conversation_id"]),
        ],
        "agent_tool_executions": [
            ("ix_agent_tool_executions_user_created", ["user_id", "created_at"]),
            ("ix_agent_tool_executions_user_id", ["user_id"]),
            ("ix_agent_tool_executions_conversation_id", ["conversation_id"]),
            ("ix_agent_tool_executions_request_id", ["request_id"]),
        ],
    }
    for table_name, specs in index_specs.items():
        if table_name not in set(inspector.get_table_names()):
            raise RuntimeError(f"Required agent table was not created: {table_name}")
        existing = {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}
        for name, columns in specs:
            if name not in existing:
                op.create_index(name, table_name, columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for table_name in ("agent_tool_executions", "agent_pending_actions", "agent_messages", "agent_conversations"):
        if table_name in tables:
            op.drop_table(table_name)
