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
    # ==================== PRE-FLIGHT: ENSURE COLUMNS EXIST ====================
    # On a fresh database, these columns may not exist yet.
    op.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE NOT NULL")
    op.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS user_name VARCHAR(100)")
    op.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS fcm_token VARCHAR(255)")
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS purchase_price NUMERIC(10,2) DEFAULT 0")

    # ==================== PRIORITY 1: CRITICAL PERFORMANCE INDEXES ====================
    # Using raw SQL with IF NOT EXISTS so this migration is fully idempotent.

    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_user_payment ON invoices (user_id, payment_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_user_date ON invoices (user_id, invoice_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_customer_id ON invoices (customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_line_items_invoice_id ON invoice_line_items (invoice_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_line_items_product_id ON invoice_line_items (product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_movements_product_id ON stock_movements (product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_movements_product_created ON stock_movements (product_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stock_movements_reference ON stock_movements (reference_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_user_active ON customers (user_id, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customers_email ON customers (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_user_active ON products (user_id, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_details_user_name ON user_details (user_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_user_details_is_active ON user_details (is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_attendance_employee_date ON attendance (employee_id, attendance_date)")

    # ==================== PRIORITY 2: DATA VALIDATION CONSTRAINTS ====================
    # Each constraint is wrapped in a DO block that checks pg_constraint first,
    # so re-running this migration never crashes.

    safe_constraints = [
        ("products", "chk_product_stock_nonnegative", "CHECK (current_stock >= 0)"),
        ("products", "chk_product_price_positive", "CHECK (unit_price > 0)"),
        ("products", "chk_product_purchase_price_nonnegative", "CHECK (purchase_price >= 0)"),
        ("invoices", "chk_invoice_total_nonnegative", "CHECK (total_amount >= 0)"),
        ("invoices", "chk_invoice_paid_nonnegative", "CHECK (paid_amount >= 0)"),
        ("invoices", "chk_invoice_paid_not_exceed_total", "CHECK (paid_amount <= total_amount)"),
        ("invoices", "chk_invoice_subtotal_nonnegative", "CHECK (subtotal >= 0)"),
        ("invoices", "chk_invoice_tax_nonnegative", "CHECK (tax >= 0)"),
        ("invoice_line_items", "chk_line_quantity_positive", "CHECK (quantity > 0)"),
        ("invoice_line_items", "chk_line_price_positive", "CHECK (unit_price > 0)"),
        ("invoice_line_items", "chk_line_total_nonnegative", "CHECK (line_total >= 0)"),
        ("payments", "chk_payment_amount_positive", "CHECK (amount > 0)"),
        ("stock_movements", "chk_movement_quantity_nonnegative", "CHECK (quantity >= 0)"),
    ]

    for table, name, check in safe_constraints:
        op.execute(f"""
            DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{name}') THEN
                    ALTER TABLE {table} ADD CONSTRAINT {name} {check};
                END IF;
            END $$;
        """)

    # ==================== PRIORITY 3: FOREIGN KEY IMPROVEMENTS ====================
    try:
        op.execute('ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoices_customer_id_fkey')
        op.execute('''
            ALTER TABLE invoices
            ADD CONSTRAINT invoices_customer_id_fkey
            FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
        ''')
    except Exception:
        pass

    try:
        op.execute('ALTER TABLE invoice_line_items DROP CONSTRAINT IF EXISTS invoice_line_items_product_id_fkey')
        op.execute('''
            ALTER TABLE invoice_line_items
            ADD CONSTRAINT invoice_line_items_product_id_fkey
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        ''')
    except Exception:
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
