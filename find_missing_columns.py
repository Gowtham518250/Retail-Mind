import os
from sqlalchemy import create_engine, text
from db import Base
import models  # Must import models to register tables in Base.metadata

DB_URL = "postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog"
engine = create_engine(DB_URL)

print("Fetching database schema via direct query...")
with engine.connect() as conn:
    # Get all tables
    res = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
    db_tables = {row[0] for row in res}
    
    # Get all columns
    res = conn.execute(text("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public';"))
    db_cols = {}
    for row in res:
        tb, col = row[0], row[1]
        if tb not in db_cols:
            db_cols[tb] = set()
        db_cols[tb].add(col)

print("Comparing database schema against SQLAlchemy models...\n")

model_tables = Base.metadata.tables.keys()

missing_tables = []
for mt in model_tables:
    if mt not in db_tables:
        missing_tables.append(mt)

print(f"Missing tables in DB ({len(missing_tables)}):")
for mt in missing_tables:
    print(f" - {mt}")

print("\nComparing columns for existing tables:")
for mt in model_tables:
    if mt in missing_tables:
        continue
    
    model_table_obj = Base.metadata.tables[mt]
    model_cols = set(model_table_obj.columns.keys())
    existing_cols = db_cols.get(mt, set())
    
    missing = model_cols - existing_cols
    if missing:
        print(f"\nTable '{mt}' has missing columns:")
        for col_name in sorted(missing):
            col_obj = model_table_obj.columns[col_name]
            print(f" - {col_name} ({col_obj.type})")
