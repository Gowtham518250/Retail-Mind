import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

conn = psycopg2.connect(DATABASE_URL, sslmode="require")

cur = conn.cursor()



olp=cur.execute("""
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'khata_history';
""")



conn.commit()


cur.close()
conn.close()
