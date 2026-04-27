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
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
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

_hf_client: InferenceClient | None = None


def _get_hf_client() -> InferenceClient | None:
    global _hf_client
    token = os.getenv("HF_TOKEN")
    if not token:
        return None
    if _hf_client is None:
        _hf_client = InferenceClient(api_key=token)
    return _hf_client


def get_ai_response(prompt: str) -> str | None:
    client = _get_hf_client()
    if client is None:
        return None
    # Calls the model in the cloud (no local download)
    response = client.chat_completion(
        model="meta-llama/Llama-3.1-8B-Instruct", 
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300
    )
    return response.choices[0].message.content