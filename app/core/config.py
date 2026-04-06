# from pydantic_settings import BaseSettings
import os
from sqlalchemy import create_engine, text
import psycopg  # pyright: ignore[reportMissingImports]
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv
_ = load_dotenv()

class Base(DeclarativeBase):
    pass

postgres_user = os.getenv('postgres_user')
postgres_password = os.getenv('postgres_password')
postgres_host = os.getenv('postgres_host')
postgres_database = os.getenv('postgres_database')
# Connect to an existing database
engine = create_engine(f"postgresql+psycopg2://{postgres_user}:{postgres_password}@{postgres_host}/{postgres_database}",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# def db_connection():
#     try:
#         with engine.connect() as connection:
#             result = connection.execute(text("SELECT version();"))
#             value = result.scalar()
#             if value:
#                 print(f"Connected to the database")
#             else:
#                 print("Connected but no version found")
#     except Exception as e:
#         print(f"Error connecting to the database: {e}")

# db_connection()