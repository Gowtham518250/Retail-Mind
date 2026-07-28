-- Create processed_operations table for idempotent operation tracking
-- This table ensures that operations are only processed once, preventing duplicates

CREATE TABLE IF NOT EXISTS processed_operations (
    id SERIAL PRIMARY KEY,
    operation_id VARCHAR(255) UNIQUE NOT NULL,  -- UUID with prefix (e.g., "create_sale_abc123")
    operation_type VARCHAR(100) NOT NULL,       -- e.g., "create_sale", "update_stock"
    user_id INTEGER NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    CONSTRAINT fk_processed_operations_user 
        FOREIGN KEY (user_id) 
        REFERENCES users(id) 
        ON DELETE CASCADE
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_processed_operations_operation_id 
    ON processed_operations(operation_id);

CREATE INDEX IF NOT EXISTS idx_processed_operations_user_id 
    ON processed_operations(user_id);

CREATE INDEX IF NOT EXISTS idx_processed_operations_processed_at 
    ON processed_operations(processed_at);

-- Create index for operation type queries
CREATE INDEX IF NOT EXISTS idx_processed_operations_operation_type 
    ON processed_operations(operation_type);

-- Add comment
COMMENT ON TABLE processed_operations IS 'Tracks processed operations for idempotency - prevents duplicate operations';
COMMENT ON COLUMN processed_operations.operation_id IS 'Unique operation identifier (UUID with prefix)';
COMMENT ON COLUMN processed_operations.operation_type IS 'Type of operation (e.g., create_sale, update_stock)';
COMMENT ON COLUMN processed_operations.user_id IS 'User who performed the operation';
COMMENT ON COLUMN processed_operations.device_id IS 'Device that initiated the operation';
COMMENT ON COLUMN processed_operations.processed_at IS 'When the operation was processed';