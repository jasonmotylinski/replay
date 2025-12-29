from models import Base, engine

# Create all tables
Base.metadata.create_all(bind=engine)

print("Database initialized!")