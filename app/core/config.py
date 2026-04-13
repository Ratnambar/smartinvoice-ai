# from pydantic_settings import BaseSettings
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from huggingface_hub import InferenceClient
from dotenv import load_dotenv
_ = load_dotenv()
from urllib.parse import quote_plus
password = quote_plus("your_password_with_@")

class Base(DeclarativeBase):
    pass

postgres_user = os.getenv('postgres_user')
postgres_password = quote_plus(os.getenv("postgres_password", ""))
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

hf_token = os.getenv('HF_TOKEN')
client = InferenceClient(api_key=hf_token)

def get_ai_response(prompt: str) -> str | None:
    # This calls the model in the cloud (no local download)
    response = client.chat_completion(
        model="meta-llama/Llama-3.1-8B-Instruct", 
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300
    )
    return response.choices[0].message.content