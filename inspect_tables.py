from sqlalchemy import create_engine, inspect

DB_URL = "postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog"
engine = create_engine(DB_URL)
inspector = inspect(engine)

print("Tables in the database:")
for table_name in inspector.get_table_names():
    print(f"Table: {table_name}")
    for column in inspector.get_columns(table_name):
        print(f"  - {column['name']}: {column['type']}")
