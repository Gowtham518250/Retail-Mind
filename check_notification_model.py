import inspect
from models import Notification

print("Notification columns in SQLAlchemy model:")
for col in Notification.__table__.columns:
    print(f" - {col.name}: {col.type}")
