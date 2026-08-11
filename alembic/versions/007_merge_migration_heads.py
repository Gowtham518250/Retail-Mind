"""Merge the legacy user_type branch with the main migration chain.

Revision ID: 007_merge_migration_heads
Revises: 006_allow_fractional_invoice_quantities, e7a9054db41d
"""

revision = "007_merge_migration_heads"
down_revision = ("006_allow_fractional_invoice_quantities", "e7a9054db41d")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
