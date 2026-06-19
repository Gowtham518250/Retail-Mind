"""
Database Cleanup Script
Drops all tables and the alembic_version table to allow fresh migration.
Run this before 'alembic upgrade head' to start with a clean database.
"""

import os
import sys
from sqlalchemy import create_engine, text

# Get database URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable not set")
    sys.exit(1)

# Replace postgres:// with postgresql:// for SQLAlchemy
DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        print("Dropping all tables...")
        
        # Drop alembic_version table first
        conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        print("✓ Dropped alembic_version table")
        
        # Get all table names
        result = conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
        """))
        
        tables = [row[0] for row in result]
        
        # Drop all tables
        for table in tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            print(f"✓ Dropped table: {table}")
        
        # Drop all enum types
        print("\nDropping all enum types...")
        result = conn.execute(text("""
            SELECT typname 
            FROM pg_type 
            WHERE typtype = 'e' 
            AND typnamespace = 'public'::regnamespace
        """))
        
        enums = [row[0] for row in result]
        
        for enum in enums:
            conn.execute(text(f"DROP TYPE IF EXISTS {enum} CASCADE"))
            print(f"✓ Dropped enum type: {enum}")
        
        conn.commit()
        print("\n✅ All tables and enum types dropped successfully")
        print("Now you can run: alembic upgrade head")
        
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
