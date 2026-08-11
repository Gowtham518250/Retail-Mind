from db import engine
from models import Base, WhatsappOrder

print("Creating new tables...")
Base.metadata.create_all(bind=engine, tables=[WhatsappOrder.__table__])
print("Done.")
