#!/usr/bin/env python3
"""
Reinitialize external database with correct schema
Drops all tables and recreates them from models
"""
import sys
import os
from sqlalchemy import inspect

print("Reinitializing External Database...")
print("=" * 70)

try:
    from db import engine, Base
    import models
    
    print("1. Inspecting current tables...")
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    print(f"   Found {len(existing_tables)} tables")
    
    print("\n2. Dropping all existing tables...")
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
    print("   ✓ All tables dropped")
    
    print("\n3. Creating new tables from models...")
    Base.metadata.create_all(bind=engine)
    print("   ✓ All tables created")
    
    print("\n4. Verifying tables...")
    inspector = inspect(engine)
    new_tables = sorted(inspector.get_table_names())
    print(f"   ✓ Total tables: {len(new_tables)}")
    
    print("\n5. Verifying key table schemas...")
    
    # Check user_details
    user_cols = {col['name'] for col in inspector.get_columns('user_details')}
    required_user_cols = {'id', 'user_name', 'email', 'password', 'user_type', 'is_active'}
    if required_user_cols.issubset(user_cols):
        print(f"   ✓ user_details: {len(user_cols)} columns")
    else:
        missing = required_user_cols - user_cols
        print(f"   ✗ user_details missing: {missing}")
    
    # Check shop_profiles
    shop_cols = {col['name'] for col in inspector.get_columns('shop_profiles')}
    required_shop_cols = {'shop_id', 'shop_name', 'address_line1', 'upi_id'}
    if required_shop_cols.issubset(shop_cols):
        print(f"   ✓ shop_profiles: {len(shop_cols)} columns")
    else:
        missing = required_shop_cols - shop_cols
        print(f"   ✗ shop_profiles missing: {missing}")
    
    print("\n" + "=" * 70)
    print("✓ Database reinitialization complete!")
    print(f"✓ {len(new_tables)} tables created successfully")
    
except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
