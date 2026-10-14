"""Add optional product image URL field.

Revision ID: 026_product_image_url
Revises: 025_online_order_payment_state
"""
from alembic import op
import sqlalchemy as sa

revision = "026_product_image_url"
down_revision = "025_online_order_payment_state"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("products", "image_url")
