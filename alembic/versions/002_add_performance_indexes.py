"""Add performance indexes and constraints

Revision ID: 002_add_performance_indexes
Revises: 001_initial_schema
Create Date: 2026-06-24

This migration adds:
- Critical performance indexes for common query patterns
- Data validation constraints to prevent invalid data
- Foreign key improvements for better data handling
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_performance_indexes'
down_revision = 'e7a9054db41d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================== PRIORITY 1: CRITICAL PERFORMANCE INDEXES ====================
    
    # Invoice table - most critical for dashboard performance
    op.create_index('ix_invoices_user_payment', 'invoices', 
                    ['user_id', 'payment_status'], unique=False)
    op.create_index('ix_invoices_user_date', 'invoices', 
                    ['user_id', sa.text('invoice_date DESC')], unique=False)
    op.create_index('ix_invoices_customer_id', 'invoices', 
                    ['customer_id'], unique=False)
    
    # InvoiceLineItem - for joining with invoices and products
    op.create_index('ix_invoice_line_items_invoice_id', 'invoice_line_items', 
                    ['invoice_id'], unique=False)
    op.create_index('ix_invoice_line_items_product_id', 'invoice_line_items', 
                    ['product_id'], unique=False)
    
    # StockMovement - for inventory tracking and history
    op.create_index('ix_stock_movements_product_id', 'stock_movements', 
                    ['product_id'], unique=False)
    op.create_index('ix_stock_movements_product_created', 'stock_movements', 
                    ['product_id', sa.text('created_at DESC')], unique=False)
    op.create_index('ix_stock_movements_reference', 'stock_movements', 
                    ['reference_id'], unique=False)
    
    # Customer - for search and filtering
    op.create_index('ix_customers_user_active', 'customers', 
                    ['user_id', 'is_active'], unique=False)
    op.create_index('ix_customers_email', 'customers', 
                    ['email'], unique=False)
    
    # Product - for search and filtering
    op.create_index('ix_products_user_active', 'products', 
                    ['user_id', 'is_active'], unique=False)
    
    # User - for authentication and filtering
    op.create_index('ix_user_details_user_name', 'user_details', 
                    ['user_name'], unique=False)
    op.create_index('ix_user_details_is_active', 'user_details', 
                    ['is_active'], unique=False)
    
    # Attendance - for employee tracking
    op.create_index('ix_attendance_employee_date', 'attendance', 
                    ['employee_id', 'attendance_date'], unique=False)
    
    # ==================== PRIORITY 2: DATA VALIDATION CONSTRAINTS ====================
    
    # Product validation
    op.execute('ALTER TABLE products ADD CONSTRAINT chk_product_stock_nonnegative CHECK (current_stock >= 0)')
    op.execute('ALTER TABLE products ADD CONSTRAINT chk_product_price_positive CHECK (unit_price > 0)')
    op.execute('ALTER TABLE products ADD CONSTRAINT chk_product_purchase_price_nonnegative CHECK (purchase_price >= 0)')
    
    # Invoice validation
    op.execute('ALTER TABLE invoices ADD CONSTRAINT chk_invoice_total_nonnegative CHECK (total_amount >= 0)')
    op.execute('ALTER TABLE invoices ADD CONSTRAINT chk_invoice_paid_nonnegative CHECK (paid_amount >= 0)')
    op.execute('ALTER TABLE invoices ADD CONSTRAINT chk_invoice_paid_not_exceed_total CHECK (paid_amount <= total_amount)')
    op.execute('ALTER TABLE invoices ADD CONSTRAINT chk_invoice_subtotal_nonnegative CHECK (subtotal >= 0)')
    op.execute('ALTER TABLE invoices ADD CONSTRAINT chk_invoice_tax_nonnegative CHECK (tax >= 0)')
    
    # InvoiceLineItem validation
    op.execute('ALTER TABLE invoice_line_items ADD CONSTRAINT chk_line_quantity_positive CHECK (quantity > 0)')
    op.execute('ALTER TABLE invoice_line_items ADD CONSTRAINT chk_line_price_positive CHECK (unit_price > 0)')
    op.execute('ALTER TABLE invoice_line_items ADD CONSTRAINT chk_line_total_nonnegative CHECK (line_total >= 0)')
    
    # Payment validation
    op.execute('ALTER TABLE payments ADD CONSTRAINT chk_payment_amount_positive CHECK (amount > 0)')
    
    # StockMovement validation
    op.execute('ALTER TABLE stock_movements ADD CONSTRAINT chk_movement_quantity_nonnegative CHECK (quantity >= 0)')
    
    # ==================== PRIORITY 3: FOREIGN KEY IMPROVEMENTS ====================
    
    # Improve foreign key delete behavior to preserve data integrity
    # Note: These require dropping and recreating constraints
    
    # Invoice.customer_id - SET NULL instead of CASCADE
    try:
        op.execute('ALTER TABLE invoices DROP CONSTRAINT invoices_customer_id_fkey')
        op.execute('''
            ALTER TABLE invoices 
            ADD CONSTRAINT invoices_customer_id_fkey 
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        ''')
    except Exception:
        # Constraint might not exist or have different name
        pass
    
    # InvoiceLineItem.product_id - SET NULL instead of CASCADE
    try:
        op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT invoice_line_items_product_id_fkey')
        op.execute('''
            ALTER TABLE invoice_line_items 
            ADD CONSTRAINT invoice_line_items_product_id_fkey 
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        ''')
    except Exception:
        # Constraint might not exist or have different name
        pass


def downgrade() -> None:
    # ==================== REVERSE PRIORITY 3: FOREIGN KEY IMPROVEMENTS ====================
    
    # Restore original CASCADE behavior
    try:
        op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT invoice_line_items_product_id_fkey')
        op.execute('''
            ALTER TABLE invoice_line_items 
            ADD CONSTRAINT invoice_line_items_product_id_fkey 
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        ''')
    except Exception:
        pass
    
    try:
        op.execute('ALTER TABLE invoices DROP CONSTRAINT invoices_customer_id_fkey')
        op.execute('''
            ALTER TABLE invoices 
            ADD CONSTRAINT invoices_customer_id_fkey 
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
        ''')
    except Exception:
        pass
    
    # ==================== REVERSE PRIORITY 2: DATA VALIDATION CONSTRAINTS ====================
    
    op.execute('ALTER TABLE stock_movements DROP CONSTRAINT chk_movement_quantity_nonnegative')
    op.execute('ALTER TABLE payments DROP CONSTRAINT chk_payment_amount_positive')
    op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT chk_line_total_nonnegative')
    op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT chk_line_price_positive')
    op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT chk_line_quantity_positive')
    op.execute('ALTER TABLE invoices DROP CONSTRAINT chk_invoice_tax_nonnegative')
    op.execute('ALTER TABLE invoices DROP CONSTRAINT chk_invoice_subtotal_nonnegative')
    op.execute('ALTER TABLE invoices DROP CONSTRAINT chk_invoice_paid_not_exceed_total')
    op.execute('ALTER TABLE invoices DROP CONSTRAINT chk_invoice_paid_nonnegative')
    op.execute('ALTER TABLE invoices DROP CONSTRAINT chk_invoice_total_nonnegative')
    op.execute('ALTER TABLE products DROP CONSTRAINT chk_product_purchase_price_nonnegative')
    op.execute('ALTER TABLE products DROP CONSTRAINT chk_product_price_positive')
    op.execute('ALTER TABLE products DROP CONSTRAINT chk_product_stock_nonnegative')
    
    # ==================== REVERSE PRIORITY 1: CRITICAL PERFORMANCE INDEXES ====================
    
    op.drop_index('ix_attendance_employee_date', 'attendance')
    op.drop_index('ix_user_details_is_active', 'user_details')
    op.drop_index('ix_user_details_user_name', 'user_details')
    op.drop_index('ix_products_user_active', 'products')
    op.drop_index('ix_customers_email', 'customers')
    op.drop_index('ix_customers_user_active', 'customers')
    op.drop_index('ix_stock_movements_reference', 'stock_movements')
    op.drop_index('ix_stock_movements_product_created', 'stock_movements')
    op.drop_index('ix_stock_movements_product_id', 'stock_movements')
    op.drop_index('ix_invoice_line_items_product_id', 'invoice_line_items')
    op.drop_index('ix_invoice_line_items_invoice_id', 'invoice_line_items')
    op.drop_index('ix_invoices_customer_id', 'invoices')
    op.drop_index('ix_invoices_user_date', 'invoices')
    op.drop_index('ix_invoices_user_payment', 'invoices')
