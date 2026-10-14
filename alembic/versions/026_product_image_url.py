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
    # Idempotent because app.py also repairs this column on older production deployments.
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT")


def downgrade():
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS image_url")
