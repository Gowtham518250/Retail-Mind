from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import StockMovement, Product
from inventory import StockMovementCreate, create_stock_movement

DB_URL = "postgresql://retail_mind_xxog_user:hjvmy6P7OxYlA7rec54JLx6OL0LlLocc@dpg-d8pnbg4m0tmc73b2ff7g-a.oregon-postgres.render.com/retail_mind_xxog"
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
db = Session()

# Mock movement payload
payload = StockMovementCreate(
    product_id=1,
    movement_type="in",
    quantity=10,
    reason="Test stock in"
)

try:
    res = create_stock_movement(payload, db)
    print("Result:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    db.rollback()
    db.close()
