from logging.config import fileConfig
from alembic import context
import os
import sys
from urllib.parse import quote_plus
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────
load_dotenv()

# ── Add your project root to path ──────────────────────
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Import your Base and ALL models ────────────────────
from app.core.config import Base, engine
from app.models.invoice_model import Vendor, Invoice, User  # import all your model files
from app.models.chunk_model import InvoiceChunk
# ── Alembic Config ─────────────────────────────────────
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what alembic uses to detect changes
target_metadata = Base.metadata


def _database_url() -> str:
    user = os.getenv("postgres_user") or os.getenv("db_user")
    password = os.getenv("postgres_password") or ""
    host = os.getenv("postgres_host")
    port = os.getenv("postgres_port", "5432")
    database = os.getenv("postgres_database")
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()