"""Add user_type to user_details

Revision ID: e7a9054db41d
Revises: 001_initial_schema
Create Date: 2026-06-19 20:02:10.916679
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e7a9054db41d'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Production databases may already contain this column while Alembic
    # revision history is being reconstructed. Only add it when absent.
    op.execute("""
        ALTER TABLE user_details
        ADD COLUMN IF NOT EXISTS user_type VARCHAR(50) DEFAULT 'OWNER' NOT NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE user_details DROP COLUMN IF EXISTS user_type")
