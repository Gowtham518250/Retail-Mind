import psycopg2

conn = psycopg2.connect(
    host="dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com",
    database="retail_mind_xxog",
    user="retail_mind_xxog_user",
    password="hjvmy6P7OxYlA7rec54JLx6OL0LlLocc",
    sslmode="require"
)

cur = conn.cursor()



olp=cur.execute("""
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'khata_history';
""")



conn.commit()


cur.close()
conn.close()