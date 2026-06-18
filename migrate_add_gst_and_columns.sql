-- Migration: Add missing columns to shop_profiles and other tables
-- Run this on your production database to fix the schema mismatch

-- ==========================================
-- Add missing columns to shop_profiles
-- ==========================================
ALTER TABLE shop_profiles
ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50);

-- Add timestamps if they don't exist
ALTER TABLE shop_profiles
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

ALTER TABLE shop_profiles
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- ==========================================
-- Verify the columns were added
-- ==========================================
-- Run this query to check:
-- SELECT column_name, data_type FROM information_schema.columns 
-- WHERE table_name='shop_profiles' ORDER BY ordinal_position;
