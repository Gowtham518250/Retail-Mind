import psycopg2

conn = psycopg2.connect(
    host="dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com",
    database="retail_mind_xxog",
    user="retail_mind_xxog_user",
    password="hjvmy6P7OxYlA7rec54JLx6OL0LlLocc",
    sslmode="require"
)

cur = conn.cursor()



cur.execute("""
ALTER TABLE gift_cards ALTER COLUMN expiry_date DROP NOT NULL;
""")

cur.execute("""
ALTER TABLE gift_cards ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
""")

cur.execute("""
UPDATE gift_cards SET is_active = TRUE WHERE is_active IS NULL;
""")

conn.commit()

print("✅ Columns added successfully")

cur.close()
conn.close()