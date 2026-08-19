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
    # Existing production databases may already have this column because
    # SQLAlchemy created the schema before Alembic was introduced.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('user_details')}
    if 'user_type' not in columns:
        op.add_column(
            'user_details',
            sa.Column('user_type', sa.String(length=50), nullable=False, server_default='OWNER')
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column['name'] for column in inspector.get_columns('user_details')}
    if 'user_type' in columns:
        op.drop_column('user_details', 'user_type')
