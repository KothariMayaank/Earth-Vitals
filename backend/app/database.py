import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


REPO_ROOT = Path(__file__).resolve().parents[2]


def get_database_url() -> str:
    load_dotenv(REPO_ROOT / ".env")
    database_url = os.getenv("SUPABASE_DB_URL")
    if not database_url:
        raise RuntimeError(
            "SUPABASE_DB_URL is not set. Copy .env.example to .env and add your "
            "Postgres connection string."
        )
    return database_url


def get_engine() -> Engine:
    return create_engine(get_database_url())
