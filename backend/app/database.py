import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DATABASE_PATH = Path(__file__).resolve().parents[1] / "data" / "jetsetgo.db"
database_url = os.getenv("DATABASE_URL", "").strip()


def sqlalchemy_database_url(value: str) -> str:
    """Convert a standard Supabase PostgreSQL URL into SQLAlchemy's psycopg form."""
    if value.startswith("postgresql://"):
        return f"postgresql+psycopg://{value.removeprefix('postgresql://')}"
    if value.startswith("postgres://"):
        return f"postgresql+psycopg://{value.removeprefix('postgres://')}"
    return value


if database_url:
    engine = create_engine(sqlalchemy_database_url(database_url), pool_pre_ping=True)
else:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DATABASE_PATH}",
        connect_args={"check_same_thread": False},
    )
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass
