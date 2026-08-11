-- ============================================================================
-- RETAIL MIND PRODUCTION MIGRATION v2.0
-- Idempotency, Duplicate Prevention, Shop Profile Persistence
-- ============================================================================
-- Run this after backup: pg_dump retail_mind_db > backup_$(date +%Y%m%d).sql
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- 1. ADD OFFLINE_ID FOR INVOICE IDEMPOTENCY
-- ============================================================================

ALTER TABLE IF EXISTS invoices 
ADD COLUMN IF NOT EXISTS offline_id VARCHAR(100);

-- Unique constraint on offline_id to prevent duplicates
ALTER TABLE IF EXISTS invoices 
ADD CONSTRAINT IF NOT EXISTS unique_offline_id UNIQUE(offline_id);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_invoices_offline_id ON invoices(offline_id);

-- ============================================================================
-- 2. ADD SYNC TRACKING COLUMNS
-- ============================================================================

ALTER TABLE IF EXISTS invoices 
ADD COLUMN IF NOT EXISTS sync_status VARCHAR(20) DEFAULT 'PENDING' 
  CHECK (sync_status IN ('PENDING', 'SYNCED', 'FAILED', 'CONFLICT'));

ALTER TABLE IF EXISTS invoices 
ADD COLUMN IF NOT EXISTS synced_at TIMESTAMP DEFAULT NULL;

-- ============================================================================
-- 3. CREATE SYNCED_SALES AUDIT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS synced_sales (
    id SERIAL PRIMARY KEY,
    sale_id VARCHAR(100) UNIQUE NOT NULL,
    invoice_id INTEGER NOT NULL,
    offline_id VARCHAR(100),
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shop_id INTEGER,
    sync_count INTEGER DEFAULT 1,
    
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (shop_id) REFERENCES shops(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_synced_sales_sale_id ON synced_sales(sale_id);
CREATE INDEX IF NOT EXISTS idx_synced_sales_offline_id ON synced_sales(offline_id);
CREATE INDEX IF NOT EXISTS idx_synced_sales_shop_id ON synced_sales(shop_id);

-- ============================================================================
-- 4. STOCK MOVEMENTS IDEMPOTENCY LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS stock_movements_log (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL,
    quantity_change INTEGER NOT NULL,
    reference_id VARCHAR(100) UNIQUE NOT NULL,
    operation_type VARCHAR(20) NOT NULL CHECK (operation_type IN ('SALE', 'ADJUSTMENT', 'RETURN', 'PURCHASE')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    invoice_id INTEGER,
    
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_reference ON stock_movements_log(reference_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements_log(product_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_created ON stock_movements_log(created_at);

-- ============================================================================
-- 5. SHOP PROFILE PERSISTENCE
-- ============================================================================

ALTER TABLE IF EXISTS shops 
ADD COLUMN IF NOT EXISTS is_online_enabled BOOLEAN DEFAULT FALSE;

ALTER TABLE IF EXISTS shops 
ADD COLUMN IF NOT EXISTS latitude FLOAT DEFAULT NULL;

ALTER TABLE IF EXISTS shops 
ADD COLUMN IF NOT EXISTS longitude FLOAT DEFAULT NULL;

ALTER TABLE IF EXISTS shops 
ADD COLUMN IF NOT EXISTS location_updated_at TIMESTAMP DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_shops_online ON shops(is_online_enabled, latitude, longitude);

-- ============================================================================
-- 6. IDEMPOTENCY CACHE TABLE (Optional - for persistent cache)
-- ============================================================================

CREATE TABLE IF NOT EXISTS idempotency_cache (
    id SERIAL PRIMARY KEY,
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    operation_type VARCHAR(50) NOT NULL,
    response_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP DEFAULT (CURRENT_TIMESTAMP + INTERVAL '1 hour'),
    
    CONSTRAINT valid_expires_at CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_idempotency_key ON idempotency_cache(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_idempotency_expires ON idempotency_cache(expires_at);

-- Clean up expired cache entries periodically
-- Run: DELETE FROM idempotency_cache WHERE expires_at < CURRENT_TIMESTAMP;

-- ============================================================================
-- 7. ADD PAYMENT TRACKING FOR RECONCILIATION
-- ============================================================================

ALTER TABLE IF EXISTS invoices 
ADD COLUMN IF NOT EXISTS payment_method VARCHAR(20) DEFAULT 'CASH';

ALTER TABLE IF EXISTS invoices 
ADD COLUMN IF NOT EXISTS reference_number VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_invoices_payment_method ON invoices(payment_method);

-- ============================================================================
-- 8. CONSTRAINTS & VALIDATION
-- ============================================================================

-- Ensure invoices have either customer name or phone
ALTER TABLE IF EXISTS invoices 
ADD CONSTRAINT IF NOT EXISTS invoice_customer_info CHECK (
    customer_name IS NOT NULL OR customer_phone IS NOT NULL
);

-- Ensure paid amount doesn't exceed total
ALTER TABLE IF EXISTS invoices 
ADD CONSTRAINT IF NOT EXISTS valid_payment_amount CHECK (
    paid_amount >= 0 AND paid_amount <= total_amount + 100  -- 100 paisa tolerance
);

-- ============================================================================
-- 9. VIEWS FOR REPORTING
-- ============================================================================

CREATE OR REPLACE VIEW v_duplicate_prevention_status AS
SELECT 
    s.id as shop_id,
    s.name as shop_name,
    COUNT(i.id) as total_invoices,
    COUNT(CASE WHEN i.offline_id IS NOT NULL THEN 1 END) as invoices_with_offline_id,
    COUNT(CASE WHEN i.sync_status = 'SYNCED' THEN 1 END) as synced_invoices,
    COUNT(CASE WHEN i.sync_status = 'PENDING' THEN 1 END) as pending_invoices
FROM shops s
LEFT JOIN invoices i ON s.id = i.shop_id
GROUP BY s.id, s.name;

CREATE OR REPLACE VIEW v_stock_deduction_audit AS
SELECT 
    p.id as product_id,
    p.name as product_name,
    COUNT(sm.id) as total_movements,
    SUM(CASE WHEN sm.operation_type = 'SALE' THEN sm.quantity_change ELSE 0 END) as total_sold,
    p.current_stock as current_stock,
    MAX(sm.created_at) as last_movement_at
FROM products p
LEFT JOIN stock_movements_log sm ON p.id = sm.product_id
GROUP BY p.id, p.name;

-- ============================================================================
-- 10. CLEANUP PROCEDURES
-- ============================================================================

-- Clean up old pending syncs (older than 7 days)
-- Run manually: DELETE FROM synced_sales WHERE synced_at < CURRENT_TIMESTAMP - INTERVAL '7 days' AND sync_count = 1;

-- Clean up expired idempotency cache
-- Run manually: DELETE FROM idempotency_cache WHERE expires_at < CURRENT_TIMESTAMP;

-- ============================================================================
-- ROLLBACK INSTRUCTIONS (if something goes wrong)
-- ============================================================================

/*
-- To rollback this migration:

ALTER TABLE invoices DROP CONSTRAINT IF EXISTS unique_offline_id;
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS invoice_customer_info;
ALTER TABLE invoices DROP CONSTRAINT IF EXISTS valid_payment_amount;
DROP INDEX IF EXISTS idx_invoices_offline_id;
DROP INDEX IF EXISTS idx_invoices_payment_method;
DROP TABLE IF EXISTS synced_sales;
DROP TABLE IF EXISTS stock_movements_log;
DROP TABLE IF EXISTS idempotency_cache;
DROP VIEW IF EXISTS v_duplicate_prevention_status;
DROP VIEW IF EXISTS v_stock_deduction_audit;

ALTER TABLE invoices DROP COLUMN IF EXISTS offline_id;
ALTER TABLE invoices DROP COLUMN IF EXISTS sync_status;
ALTER TABLE invoices DROP COLUMN IF EXISTS synced_at;
ALTER TABLE invoices DROP COLUMN IF EXISTS payment_method;
ALTER TABLE invoices DROP COLUMN IF EXISTS reference_number;

ALTER TABLE shops DROP COLUMN IF EXISTS is_online_enabled;
ALTER TABLE shops DROP COLUMN IF EXISTS latitude;
ALTER TABLE shops DROP COLUMN IF EXISTS longitude;
ALTER TABLE shops DROP COLUMN IF EXISTS location_updated_at;
DROP INDEX IF EXISTS idx_shops_online;
*/

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check if migration was successful
SELECT 
    'invoices table' as object,
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='invoices' AND column_name='offline_id') as has_offline_id,
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='synced_sales') as has_synced_sales,
    EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='stock_movements_log') as has_stock_log,
    EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='shops' AND column_name='is_online_enabled') as has_online_flag;

COMMIT;

-- ============================================================================
-- POST-MIGRATION CHECKS
-- ============================================================================

-- Verify all offline_id values are unique
SELECT offline_id, COUNT(*) as count 
FROM invoices 
WHERE offline_id IS NOT NULL 
GROUP BY offline_id 
HAVING COUNT(*) > 1;
-- Expected: 0 rows (no duplicates)

-- Check sync status distribution
SELECT sync_status, COUNT(*) as count FROM invoices GROUP BY sync_status;
-- Expected: Some PENDING, some SYNCED

-- Verify stock movements are tracked
SELECT COUNT(*) as total_stock_movements FROM stock_movements_log;
-- Expected: > 0 if migrations applied to existing data

-- Check online shops count
SELECT COUNT(*) as online_shops FROM shops WHERE is_online_enabled = TRUE;
-- Expected: 0 (until toggles are enabled)
