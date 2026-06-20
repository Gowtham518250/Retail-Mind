from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True) # Ensure we get the correct DB URL used by app

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    print("FATAL: No DATABASE_URL found.")
    exit(1)

# Fix postgres prefix if needed
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

print(f"Connecting to database to apply patch...")
engine = create_engine(DB_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE invoices ADD COLUMN offline_id VARCHAR(50);"))
        print("✅ Successfully added offline_id column to invoices table.")
    except Exception as e:
        print(f"⚠️ Warning adding offline_id (might already exist): {e}")
        
    try:
        conn.execute(text("CREATE UNIQUE INDEX ix_invoices_offline_id ON invoices (offline_id);"))
        print("✅ Successfully added unique index on offline_id.")
    except Exception as e:
        print(f"⚠️ Warning adding index (might already exist): {e}")
        
    conn.commit()

print("Database patch complete!")
