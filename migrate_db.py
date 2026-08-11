import models
from db import engine, Base

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Database updated successfully!")
