"""Safely copy the existing JetSetGo SQLite data into the configured PostgreSQL database.

Run from backend/ after DATABASE_URL points to a working Supabase Session pooler:
    .venv/bin/python scripts/migrate_sqlite_to_supabase.py --apply
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import models  # noqa: F401 - register the SQLAlchemy models with Base
from app.database import Base, sqlalchemy_database_url


TABLE_ORDER = ("users", "trips", "activities", "scheduled_activities", "trip_members", "votes")
DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "data" / "jetsetgo.db"


def source_counts(source_engine, source_metadata: MetaData) -> dict[str, int]:
    """Return source row counts for every table that exists in the legacy database."""
    with source_engine.connect() as connection:
        return {
            name: connection.execute(select(func.count()).select_from(source_metadata.tables[name])).scalar_one()
            for name in TABLE_ORDER
            if name in source_metadata.tables
        }


def destination_counts(destination_engine) -> dict[str, int]:
    """Return row counts from destination tables that already exist."""
    existing = set(inspect(destination_engine).get_table_names())
    with destination_engine.connect() as connection:
        return {
            name: connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()
            for name in TABLE_ORDER
            if name in existing
        }


def copy_records(source_engine, destination_engine) -> dict[str, int]:
    """Create the current schema and copy legacy rows in foreign-key-safe order."""
    source_metadata = MetaData()
    source_metadata.reflect(source_engine)
    source_summary = source_counts(source_engine, source_metadata)
    existing_counts = destination_counts(destination_engine)
    if any(existing_counts.values()):
        raise RuntimeError("The destination database already contains JetSetGo data; refusing to merge automatically.")

    Base.metadata.create_all(destination_engine)
    copied: dict[str, int] = {}
    with destination_engine.begin() as destination_connection, source_engine.connect() as source_connection:
        for name in TABLE_ORDER:
            if name not in source_metadata.tables:
                continue
            source_table = source_metadata.tables[name]
            destination_table = Base.metadata.tables[name]
            shared_columns = [column.name for column in destination_table.columns if column.name in source_table.columns]
            rows = [dict(row) for row in source_connection.execute(select(*(source_table.c[column] for column in shared_columns))).mappings()]
            if rows:
                destination_connection.execute(destination_table.insert(), rows)
            copied[name] = len(rows)

        if destination_engine.dialect.name == "postgresql":
            for name, count in copied.items():
                if count:
                    destination_connection.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{name}', 'id'), "
                            f"(SELECT MAX(id) FROM {name}), true)"
                        )
                    )
    return copied


def main() -> None:
    """Preview or apply the one-time SQLite-to-Supabase migration."""
    parser = argparse.ArgumentParser(description="Migrate JetSetGo SQLite data into Supabase PostgreSQL.")
    parser.add_argument("--apply", action="store_true", help="Perform the migration. Without it, only show source counts.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Path to the legacy SQLite database.")
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required.")
    if not args.source.is_file():
        raise SystemExit(f"SQLite source database was not found: {args.source}")

    source_engine = create_engine(f"sqlite:///{args.source}")
    destination_engine = create_engine(sqlalchemy_database_url(database_url), pool_pre_ping=True)
    source_metadata = MetaData()
    source_metadata.reflect(source_engine)
    counts = source_counts(source_engine, source_metadata)
    print("SQLite source rows:", ", ".join(f"{name}={count}" for name, count in counts.items()) or "none")
    if not args.apply:
        print("Dry run only. Re-run with --apply to create the Supabase schema and copy these records.")
        return

    copied = copy_records(source_engine, destination_engine)
    print("Migration complete:", ", ".join(f"{name}={count}" for name, count in copied.items()) or "no rows copied")


if __name__ == "__main__":
    main()
