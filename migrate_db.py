from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

database_url = os.getenv("DATABASE_URL")
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

print(f"Connecting to {database_url}...")
engine = create_engine(database_url)

commands = [
    "ALTER TABLE stock_movements ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE leave_requests ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE customers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50);",
    "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS gst_number VARCHAR(50);",
    "ALTER TABLE shop_profiles ADD COLUMN IF NOT EXISTS logo_url VARCHAR(500);",
    "ALTER TABLE online_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"
]

try:
    with engine.begin() as conn:
        for cmd in commands:
            print(f"Executing: {cmd}")
            conn.execute(text(cmd))
    print("Database schema migration successful!")
except Exception as e:
    print(f"Migration error: {e}")
