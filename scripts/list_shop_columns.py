import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import sessionLocal
from sqlalchemy import text

db = sessionLocal()
try:
    cols = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='shop_profiles' ORDER BY ordinal_position")).fetchall()
    print([c[0] for c in cols])
finally:
    db.close()
