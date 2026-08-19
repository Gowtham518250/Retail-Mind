"""Merge the invoice-discount and attendance migration heads.

Revision ID: 009_merge_invoice_and_attendance_heads
Revises: 008_add_invoice_line_discount_amount, 008_attendance_nullsafe_unique
"""

revision = "009_merge_invoice_and_attendance_heads"
down_revision = (
    "008_add_invoice_line_discount_amount",
    "008_attendance_nullsafe_unique",
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
