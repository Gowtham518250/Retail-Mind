from sqlalchemy import create_engine, text

# Hardcode external PostgreSQL URL from Render
DB_URL = "postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog"

print(f"Connecting to live Render PostgreSQL database to apply patch...")
engine = create_engine(DB_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE online_customers ALTER COLUMN email DROP NOT NULL;"))
        print("✅ Successfully made email optional in online_customers table.")
    except Exception as e:
        print(f"⚠️ Warning altering online_customers (might already be optional): {e}")
        
    conn.commit()

print("Database patch complete!")
