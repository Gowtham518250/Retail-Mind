#!/usr/bin/env python3
"""Add missing columns to user_details table"""
import sys
from sqlalchemy import text
from db import engine

print("Adding missing columns to external database...")
print("=" * 70)

migrations = [
    # User details
    "ALTER TABLE user_details ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
]

try:
    with engine.connect() as conn:
        for migration in migrations:
            try:
                print(f"Executing: {migration[:60]}...")
                conn.execute(text(migration))
                conn.commit()
                print("  ✓ Success")
            except Exception as e:
                if "already exists" in str(e) or "duplicate" in str(e).lower():
                    print(f"  ℹ Already exists")
                else:
                    print(f"  ✗ Error: {e}")
                    conn.rollback()
    
    print("\n✓ Database migration complete!")
    
except Exception as e:
    print(f"✗ Fatal error: {e}")
    sys.exit(1)

print("=" * 70)
