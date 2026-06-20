"""Add user_type to user_details

Revision ID: e7a9054db41d
Revises: 001_initial_schema
Create Date: 2026-06-19 20:02:10.916679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7a9054db41d'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_details', sa.Column('user_type', sa.String(length=50), nullable=False, server_default='OWNER'))

def downgrade() -> None:
    op.drop_column('user_details', 'user_type')
