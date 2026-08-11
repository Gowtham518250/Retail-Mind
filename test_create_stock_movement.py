import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import StockMovement, Product
from datetime import datetime

DB_URL = os.getenv("DATABASE_URL")
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
db = Session()

try:
    # Let's try to add a StockMovement for product_id=1
    sm = StockMovement(
        product_id=1,
        movement_type="IN",
        quantity=5,
        reason="Test",
        reference_id="ref123"
    )
    db.add(sm)
    db.commit()
    print("Success inserting StockMovement!")
except Exception as e:
    db.rollback()
    print("Error inserting StockMovement:", e)
finally:
    db.close()
