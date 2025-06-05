from sqlmodel import create_engine, Session
from backend.settings import settings

# Database Setup
DATABASE_URL = str(settings.DATABASE_URL)  # Ensure it's a string
engine = create_engine(DATABASE_URL)  # echo=True for debugging SQL can be added here if needed globally

# Dependency to get DB session
def get_db_session():
    with Session(engine) as session:
        yield session

# If you had a create_db_and_tables function in main.py that was called on startup
# for local development (often commented out or removed when using Alembic),
# you might move it here as well, or handle it as part of your Alembic setup.
# Example:
# def create_db_and_tables():
#     SQLModel.metadata.create_all(engine) # Ensure all models are imported for this to work
