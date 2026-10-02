import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from db import sessionLocal
from sqlalchemy import text

db = sessionLocal()
try:
    res = db.execute(text("""
        INSERT INTO shop_profiles (shop_id, shop_name, shop_description, logo_url, is_online_store_enabled, is_active, created_at, updated_at)
        VALUES (:shop_id, :shop_name, :shop_description, :logo_url, true, true, now(), now())
        RETURNING id
    """), {
        'shop_id': 1,
        'shop_name': 'Demo Shop',
        'shop_description': 'Demo shop for testing metadata injection',
        'logo_url': 'https://example.com/logo.png'
    })
    db.commit()
    new_id = res.fetchone()[0]
    print('inserted', new_id)
finally:
    db.close()
