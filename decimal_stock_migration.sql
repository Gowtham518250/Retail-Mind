-- Retail Mind V4: preserve fractional inventory quantities.
-- Run in a maintenance window after a backup.
BEGIN;

ALTER TABLE products
  ALTER COLUMN current_stock TYPE NUMERIC(12,3)
  USING current_stock::NUMERIC(12,3);

ALTER TABLE stock_movements
  ALTER COLUMN quantity TYPE NUMERIC(12,3)
  USING quantity::NUMERIC(12,3);

ALTER TABLE product_batches
  ALTER COLUMN quantity TYPE NUMERIC(12,3)
  USING quantity::NUMERIC(12,3);

COMMIT;
