# from pydantic_settings import BaseSettings
import os
import psycopg2
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from huggingface_hub import InferenceClient

from dotenv import load_dotenv

_ = load_dotenv()
from urllib.parse import quote_plus
# password = quote_plus("your_password_with_@")





class Base(DeclarativeBase):
    pass


postgres_user = os.getenv('postgres_user')
# postgres_password = quote_plus(os.getenv("postgres_password", get_auth_token()))
postgres_host = os.getenv('postgres_host')
postgres_port = os.getenv('postgres_port')
postgres_database = os.getenv('postgres_database')
aws_region = os.getenv('aws_region')
redis_url = os.getenv('aws_redis', 'redis://redis:6379/0')


def get_auth_token():
    port = int(postgres_port or 5432)
    auth_token = boto3.client("rds", region_name=aws_region).generate_db_auth_token(
        DBHostname=postgres_host,
        Port=port,
        DBUsername=postgres_user,
        Region=aws_region,
    )
    return auth_token

# auth_token = get_auth_token()


def get_connection():
    """Connection creator — SQLAlchemy calls this for each new connection"""
    token = get_auth_token()  # Fresh token every time a new connection is made
    port = int(postgres_port or 5432)
    conn = psycopg2.connect(
        host=postgres_host,
        port=port,
        database=postgres_database,
        user=postgres_user,
        password=token,
        sslmode="require",
    )
    return conn


engine = create_engine(
    "postgresql+psycopg2://",   # dummy URL, overridden by creator
    creator=get_connection,      # ← this is the key change
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=600,            # recycle connections every 10 mins (token expires in 15)
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