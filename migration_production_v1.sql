-- =========================================================================
-- AI SHOP PRO - COMPREHENSIVE DATABASE MIGRATION
-- =========================================================================
-- For production deployment on Render/Railway
-- Includes all 43 models with proper schema, indexes, and constraints
-- =========================================================================

-- =========================================================================
-- SECTION 1: EXISTING TABLE UPGRADES
-- =========================================================================

-- Update shop_profiles to add missing columns
ALTER TABLE IF EXISTS shop_profiles
ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50),
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- =========================================================================
-- SECTION 2: CORE TABLES
-- =========================================================================

-- ==================== USER & AUTHENTICATION ====================

CREATE TABLE IF NOT EXISTS password_reset (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    reset_token VARCHAR(255) UNIQUE NOT NULL,
    token_expiry TIMESTAMP NOT NULL,
    is_used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_password_reset_user_id ON password_reset(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset(reset_token);

CREATE TABLE IF NOT EXISTS token (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    token_type VARCHAR(50) DEFAULT 'bearer',
    expires_in INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_token_user_id ON token(user_id);

-- ==================== SESSION MANAGEMENT ====================

CREATE TABLE IF NOT EXISTS refresh_token (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    token VARCHAR(500) NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_refresh_token_user_id ON refresh_token(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_token_expires_at ON refresh_token(expires_at);

CREATE TABLE IF NOT EXISTS session_token (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    session_id VARCHAR(500) UNIQUE NOT NULL,
    device_info TEXT,
    ip_address VARCHAR(45),
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_session_token_user_id ON session_token(user_id);
CREATE INDEX IF NOT EXISTS idx_session_token_session_id ON session_token(session_id);

CREATE TABLE IF NOT EXISTS offline_data_queue (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id INTEGER,
    data_json JSONB,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_offline_data_queue_user_id ON offline_data_queue(user_id);
CREATE INDEX IF NOT EXISTS idx_offline_data_queue_status ON offline_data_queue(status);

-- ==================== INVENTORY ====================

CREATE TABLE IF NOT EXISTS stock_movements (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    movement_type VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    reason VARCHAR(200),
    reference_id VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product_id ON stock_movements(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_created_at ON stock_movements(created_at);

CREATE TABLE IF NOT EXISTS product_batches (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_number VARCHAR(100) UNIQUE,
    manufacture_date DATE,
    expiry_date DATE,
    quantity INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_product_batches_product_id ON product_batches(product_id);
CREATE INDEX IF NOT EXISTS idx_product_batches_expiry_date ON product_batches(expiry_date);

-- ==================== ATTENDANCE & HR ====================

CREATE TABLE IF NOT EXISTS leave_requests (
    id SERIAL PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    leave_type VARCHAR(50) NOT NULL,
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee_id ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status ON leave_requests(status);

CREATE TABLE IF NOT EXISTS worker (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    role VARCHAR(100),
    hourly_rate NUMERIC(10, 2),
    total_hours_worked FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_worker_user_id ON worker(user_id);
CREATE INDEX IF NOT EXISTS idx_worker_shop_id ON worker(shop_id);

-- ==================== CUSTOMERS ====================

CREATE TABLE IF NOT EXISTS customer_credit_score (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
    score FLOAT DEFAULT 100.0,
    max_credit_allowed NUMERIC(10, 2),
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_credit_score_customer_id ON customer_credit_score(customer_id);

-- ==================== INVOICES & PAYMENTS ====================

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255),
    quantity INTEGER NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    discount_percent NUMERIC(5, 2) DEFAULT 0,
    tax_percent NUMERIC(5, 2) DEFAULT 0,
    line_total NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_invoice_line_items_invoice_id ON invoice_line_items(invoice_id);

CREATE TABLE IF NOT EXISTS payment (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    amount NUMERIC(12, 2) NOT NULL,
    payment_method VARCHAR(100),
    transaction_id VARCHAR(255),
    payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'COMPLETED'
);
CREATE INDEX IF NOT EXISTS idx_payment_invoice_id ON payment(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payment_user_id ON payment(user_id);

CREATE TABLE IF NOT EXISTS notification (
    id SERIAL PRIMARY KEY,
    invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    notification_type VARCHAR(100),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_notification_user_id ON notification(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_invoice_id ON notification(invoice_id);

-- ==================== LOYALTY ====================

CREATE TABLE IF NOT EXISTS loyalty_tier (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    tier_name VARCHAR(100) NOT NULL,
    min_points INTEGER,
    discount_percent NUMERIC(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loyalty_tier_shop_id ON loyalty_tier(shop_id);

CREATE TABLE IF NOT EXISTS customer_loyalty (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    loyalty_tier_id INTEGER REFERENCES loyalty_tier(id) ON DELETE SET NULL,
    points_balance INTEGER DEFAULT 0,
    total_spent NUMERIC(12, 2) DEFAULT 0,
    last_transaction_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_loyalty_customer_id ON customer_loyalty(customer_id);

CREATE TABLE IF NOT EXISTS loyalty_transaction (
    id SERIAL PRIMARY KEY,
    customer_loyalty_id INTEGER NOT NULL REFERENCES customer_loyalty(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50),
    points_change INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_loyalty_transaction_customer_loyalty_id ON loyalty_transaction(customer_loyalty_id);

-- ==================== DELIVERY ====================

CREATE TABLE IF NOT EXISTS delivery (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES online_orders(id) ON DELETE SET NULL,
    driver_name VARCHAR(100),
    driver_phone VARCHAR(20),
    vehicle_number VARCHAR(50),
    estimated_delivery_date DATE,
    actual_delivery_date DATE,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_delivery_order_id ON delivery(order_id);
CREATE INDEX IF NOT EXISTS idx_delivery_status ON delivery(status);

CREATE TABLE IF NOT EXISTS delivery_tracking (
    id SERIAL PRIMARY KEY,
    delivery_id INTEGER NOT NULL REFERENCES delivery(id) ON DELETE CASCADE,
    location VARCHAR(300),
    latitude FLOAT,
    longitude FLOAT,
    status VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_delivery_tracking_delivery_id ON delivery_tracking(delivery_id);

-- ==================== SHOP CONFIGURATION ====================

CREATE TABLE IF NOT EXISTS billing_template (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    template_name VARCHAR(255),
    header_text TEXT,
    footer_text TEXT,
    logo_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_billing_template_shop_id ON billing_template(shop_id);

CREATE TABLE IF NOT EXISTS billing_counter (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    counter_name VARCHAR(100),
    counter_number INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_billing_counter_shop_id ON billing_counter(shop_id);

-- ==================== FINANCIAL & LEDGER ====================

CREATE TABLE IF NOT EXISTS khata_balance (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    balance NUMERIC(12, 2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_khata_balance_customer_id ON khata_balance(customer_id);

CREATE TABLE IF NOT EXISTS khata_history (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    transaction_type VARCHAR(50),
    amount NUMERIC(12, 2),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_khata_history_customer_id ON khata_history(customer_id);
CREATE INDEX IF NOT EXISTS idx_khata_history_created_at ON khata_history(created_at);

CREATE TABLE IF NOT EXISTS shop_expense (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    category VARCHAR(100),
    amount NUMERIC(12, 2) NOT NULL,
    description TEXT,
    expense_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_shop_expense_shop_id ON shop_expense(shop_id);
CREATE INDEX IF NOT EXISTS idx_shop_expense_expense_date ON shop_expense(expense_date);

CREATE TABLE IF NOT EXISTS upi_ledger (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    transaction_id VARCHAR(255) UNIQUE,
    amount NUMERIC(12, 2) NOT NULL,
    upi_id VARCHAR(100),
    status VARCHAR(50) DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_upi_ledger_shop_id ON upi_ledger(shop_id);
CREATE INDEX IF NOT EXISTS idx_upi_ledger_created_at ON upi_ledger(created_at);

CREATE TABLE IF NOT EXISTS universal_transaction (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    transaction_type VARCHAR(100),
    entity_type VARCHAR(100),
    entity_id INTEGER,
    amount NUMERIC(12, 2),
    reference_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_universal_transaction_shop_id ON universal_transaction(shop_id);
CREATE INDEX IF NOT EXISTS idx_universal_transaction_created_at ON universal_transaction(created_at);

-- ==================== REPORTING ====================

CREATE TABLE IF NOT EXISTS sales_by_counter (
    id SERIAL PRIMARY KEY,
    counter_id INTEGER NOT NULL REFERENCES billing_counter(id) ON DELETE CASCADE,
    sale_date DATE,
    total_sales NUMERIC(12, 2),
    transaction_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sales_by_counter_counter_id ON sales_by_counter(counter_id);
CREATE INDEX IF NOT EXISTS idx_sales_by_counter_sale_date ON sales_by_counter(sale_date);

CREATE TABLE IF NOT EXISTS daily_report (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    report_date DATE,
    total_sales NUMERIC(12, 2),
    total_expenses NUMERIC(12, 2),
    profit NUMERIC(12, 2),
    transaction_count INTEGER,
    customer_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_daily_report_shop_id ON daily_report(shop_id);
CREATE INDEX IF NOT EXISTS idx_daily_report_report_date ON daily_report(report_date);

-- ==================== CUSTOMER EXPERIENCE ====================

CREATE TABLE IF NOT EXISTS customer_occasion (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    occasion_type VARCHAR(100),
    occasion_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_customer_occasion_customer_id ON customer_occasion(customer_id);

CREATE TABLE IF NOT EXISTS festival_event (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    festival_name VARCHAR(255),
    start_date DATE,
    end_date DATE,
    discount_percent NUMERIC(5, 2),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_festival_event_shop_id ON festival_event(shop_id);
CREATE INDEX IF NOT EXISTS idx_festival_event_is_active ON festival_event(is_active);

CREATE TABLE IF NOT EXISTS chatbot_context (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    context_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==================== E-COMMERCE & B2B ====================

CREATE TABLE IF NOT EXISTS purchase_order (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    vendor_name VARCHAR(255),
    order_date DATE,
    expected_delivery_date DATE,
    status VARCHAR(50) DEFAULT 'PENDING',
    total_amount NUMERIC(12, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_purchase_order_shop_id ON purchase_order(shop_id);
CREATE INDEX IF NOT EXISTS idx_purchase_order_status ON purchase_order(status);

CREATE TABLE IF NOT EXISTS bank_reconciliation (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    bank_statement_date DATE,
    bank_statement_amount NUMERIC(12, 2),
    book_balance NUMERIC(12, 2),
    variance NUMERIC(12, 2),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bank_reconciliation_shop_id ON bank_reconciliation(shop_id);

-- ==================== GIFT CARDS ====================

CREATE TABLE IF NOT EXISTS gift_card (
    id SERIAL PRIMARY KEY,
    shop_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    card_code VARCHAR(100) UNIQUE,
    denomination NUMERIC(10, 2),
    balance NUMERIC(10, 2),
    is_active BOOLEAN DEFAULT TRUE,
    expiry_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gift_card_shop_id ON gift_card(shop_id);
CREATE INDEX IF NOT EXISTS idx_gift_card_card_code ON gift_card(card_code);

-- ==================== NOTIFICATIONS ====================

CREATE TABLE IF NOT EXISTS email_notification (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    recipient_email VARCHAR(255),
    subject VARCHAR(255),
    body TEXT,
    status VARCHAR(50) DEFAULT 'PENDING',
    sent_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_email_notification_user_id ON email_notification(user_id);
CREATE INDEX IF NOT EXISTS idx_email_notification_status ON email_notification(status);

-- ==================== BATCH OPERATIONS ====================

CREATE TABLE IF NOT EXISTS batch_operations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES user_details(id) ON DELETE CASCADE,
    operation_type VARCHAR(50),
    entity_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'PROCESSING',
    total_records INTEGER,
    processed_records INTEGER DEFAULT 0,
    failed_records INTEGER DEFAULT 0,
    file_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_batch_operations_user_id ON batch_operations(user_id);
CREATE INDEX IF NOT EXISTS idx_batch_operations_status ON batch_operations(status);

-- =========================================================================
-- SECTION 3: INDEXES FOR PERFORMANCE
-- =========================================================================

-- Common search patterns
CREATE INDEX IF NOT EXISTS idx_user_email_lower ON user_details(LOWER(email));
CREATE INDEX IF NOT EXISTS idx_customer_phone_lower ON customers(LOWER(phone));
CREATE INDEX IF NOT EXISTS idx_products_user_active ON products(user_id, is_active);
CREATE INDEX IF NOT EXISTS idx_invoices_user_created ON invoices(user_id, created_at DESC);

-- =========================================================================
-- SECTION 4: AUDIT LOGGING
-- =========================================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES user_details(id) ON DELETE CASCADE,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp DESC);

-- =========================================================================
-- SECTION 5: VERIFICATION QUERIES
-- =========================================================================

-- Run these after migration to verify:
/*
SELECT COUNT(*) as total_tables FROM information_schema.tables WHERE table_schema = 'public';
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;

-- Check shop_profiles has gst_number:
SELECT column_name FROM information_schema.columns WHERE table_name='shop_profiles' ORDER BY ordinal_position;

-- Count total indexes:
SELECT COUNT(*) as total_indexes FROM pg_indexes WHERE schemaname = 'public';
*/

-- =========================================================================
-- END OF MIGRATION
-- =========================================================================
