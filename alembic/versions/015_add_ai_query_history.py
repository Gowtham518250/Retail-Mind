"""Persist owner AI business-query questions and answers.

Revision ID: 015_add_ai_query_history
Revises: 014_marketplace_reviews_and_ratings
Create Date: 2026-10-01
"""

from alembic import op
import sqlalchemy as sa


revision = "015_add_ai_query_history"
down_revision = "014_marketplace_reviews_and_ratings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_query_history",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user_details.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_ai_query_history_user_id",
        "ai_query_history",
        ["user_id"],
    )
    op.create_index(
        "ix_ai_query_history_created_at",
        "ai_query_history",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_query_history_created_at", table_name="ai_query_history")
    op.drop_index("ix_ai_query_history_user_id", table_name="ai_query_history")
    op.drop_table("ai_query_history")
