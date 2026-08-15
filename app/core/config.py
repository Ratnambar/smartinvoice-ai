import os
import psycopg2
import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from huggingface_hub import InferenceClient

from dotenv import load_dotenv

_ = load_dotenv()

class Base(DeclarativeBase):
    pass


db_user = os.getenv("postgres_user") or os.getenv("db_user")
# Plain secret for psycopg2 (do not URL-encode). If unset/empty, IAM token is used in get_connection().
postgres_password = os.getenv("postgres_password") or None
postgres_host = os.getenv("postgres_host")
postgres_port = os.getenv('postgres_port')
postgres_database = os.getenv('postgres_database')
aws_region = os.getenv('aws_region')
redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "500"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "80"))
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() in ("true", "1", "yes")


# def get_auth_token():
#     port = int(postgres_port or 5432)
#     auth_token = boto3.client("rds", region_name=aws_region).generate_db_auth_token(
#         DBHostname=postgres_host,
#         Port=port,
#         DBUsername=db_user,
#         Region=aws_region,
#     )
#     return auth_token

# auth_token = get_auth_token()


def get_connection():
    """Connection creator — SQLAlchemy calls this for each new connection."""
    port = int(postgres_port or 5432)
    # password = postgres_password if postgres_password else get_auth_token()
    connect_kwargs: dict = {
        "host": postgres_host,
        "port": port,
        "database": postgres_database,
        "user": db_user,
        "password": postgres_password,
    }
    sslmode = os.getenv("postgres_sslmode")
    if sslmode is None:
        # RDS requires SSL; local Postgres typically does not support it.
        sslmode = "require" if postgres_host and "rds.amazonaws.com" in postgres_host else "disable"
    if sslmode != "disable":
        connect_kwargs["sslmode"] = sslmode
    conn = psycopg2.connect(**connect_kwargs)
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