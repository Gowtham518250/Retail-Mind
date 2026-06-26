"""add timestamps to shop models

Revision ID: 004
Revises: e7a9054db41d
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Add created_at and updated_at to shop_profiles
    op.add_column('shop_profiles', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('shop_profiles', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Add created_at and updated_at to shop_settings
    op.add_column('shop_settings', sa.Column('created_at', sa.DateTime(), nullable=True))
    op.add_column('shop_settings', sa.Column('updated_at', sa.DateTime(), nullable=True))
    
    # Set default values for existing records
    bind = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(bind=bind, only=['shop_profiles', 'shop_settings'])
    
    shop_profiles = metadata.tables['shop_profiles']
    shop_settings = metadata.tables['shop_settings']
    
    # Update existing rows with current time
    bind.execute(
        sa.update(shop_profiles).values(
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    )
    bind.execute(
        sa.update(shop_settings).values(
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    )


def downgrade():
    # Remove created_at and updated_at from shop_settings
    op.drop_column('shop_settings', 'updated_at')
    op.drop_column('shop_settings', 'created_at')
    
    # Remove created_at and updated_at from shop_profiles
    op.drop_column('shop_profiles', 'updated_at')
    op.drop_column('shop_profiles', 'created_at')
