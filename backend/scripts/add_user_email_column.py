"""Add the authenticated-email field to existing JetSetGo user profiles.

Run from backend/ after DATABASE_URL is configured:
    .venv/bin/python scripts/add_user_email_column.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import engine


def main() -> None:
    """Preview or apply the additive email-column migration without touching existing records."""
    parser = argparse.ArgumentParser(description="Add users.email for Supabase-linked profiles.")
    parser.add_argument("--apply", action="store_true", help="Apply the database change. Without it, only report current state.")
    args = parser.parse_args()
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    if "email" in columns:
        print("users.email already exists; no migration is needed.")
        return
    if not args.apply:
        print("users.email is missing. Re-run with --apply to add it and its unique index.")
        return
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
            connection.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
        else:
            connection.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
            connection.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
    print("Added users.email and its unique index. Existing users will receive email values on their next authenticated request.")


if __name__ == "__main__":
    main()
