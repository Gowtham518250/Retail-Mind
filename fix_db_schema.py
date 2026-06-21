from sqlalchemy import create_engine, text

# Hardcode external PostgreSQL URL from Render
DB_URL = "postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog"

print(f"Connecting to live Render PostgreSQL database to apply patch...")
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
