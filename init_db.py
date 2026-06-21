#!/usr/bin/env python3
"""Initialize database schema"""

from db import engine, Base
import models
import sys

try:
    Base.metadata.create_all(bind=engine)
    print("✓ Database tables created/verified successfully!")
    
    # List created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"\n✓ Total tables: {len(tables)}")
    print("\nTables created:")
    for table in sorted(tables):
        print(f"  - {table}")
except Exception as e:
    print(f"✗ Error: {type(e).__name__}")
    print(f"  {str(e)[:500]}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
