import inspect
from models import Customer

print("Customer columns in SQLAlchemy model:")
for col in Customer.__table__.columns:
    print(f" - {col.name}: {col.type}")
