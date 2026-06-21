#!/usr/bin/env python3
"""Drop and recreate tables with correct schema"""

from sqlalchemy import text
from db import engine, Base
import models

print("Fixing Database Schema...")
print("=" * 70)

try:
    with engine.connect() as conn:
        # Get all table names
        inspector_result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        tables = [row[0] for row in inspector_result]
        print(f"Found {len(tables)} existing tables")
        
        if tables:
            print("\nDropping all tables...")
            # Drop all tables (PostgreSQL will handle foreign keys)
            conn.execute(text("DROP TABLE IF EXISTS " + ", ".join(f'"{t}"' for t in reversed(tables)) + " CASCADE"))
            conn.commit()
            print("[OK] All tables dropped")
        
        print("\nRecreating all tables from models...")
        conn.close()
    
    # Recreate all tables
    Base.metadata.create_all(bind=engine)
    print("[OK] All tables recreated with correct schema")
    
    print("\nValidating schema...")
    with engine.connect() as conn:
        # Check shop_profiles columns
        inspector_result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'shop_profiles'
            ORDER BY ordinal_position
        """))
        columns = [row[0] for row in inspector_result]
        print(f"\nshop_profiles table columns ({len(columns)}):")
        for col in columns[:10]:
            print(f"  - {col}")
        if len(columns) > 10:
            print(f"  ... and {len(columns) - 10} more columns")
        
        # Check for critical columns
        critical = ['address_line1', 'address_line2', 'city', 'state', 'postal_code', 'pan_number']
        missing = [col for col in critical if col not in columns]
        if missing:
            print(f"\n[FAIL] Missing critical columns: {', '.join(missing)}")
        else:
            print(f"\n[OK] All critical columns present")

except Exception as e:
    print(f"\n[FAIL] ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
