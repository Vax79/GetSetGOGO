"""Add username/password-session schema support to an existing JetSetGo database.

Run from backend/ after DATABASE_URL is configured:
    .venv/bin/python scripts/migrate_username_auth.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import models  # noqa: F401 - register AuthSession metadata
from app.database import Base, engine


def main() -> None:
    """Preview or apply the additive username/password schema migration."""
    parser = argparse.ArgumentParser(description="Add JetSetGo username/password authentication schema.")
    parser.add_argument("--apply", action="store_true", help="Apply the schema changes. Without it, only report state.")
    args = parser.parse_args()
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    missing = [name for name in ("username", "password_hash") if name not in columns]
    has_sessions = "auth_sessions" in inspect(engine).get_table_names()
    if not missing and has_sessions:
        print("Username/password schema already exists; no migration is needed.")
        return
    if not args.apply:
        print(f"Missing user columns: {', '.join(missing) or 'none'}; auth_sessions exists: {has_sessions}.")
        print("Re-run with --apply to add the missing schema.")
        return
    with engine.begin() as connection:
        if "username" in missing:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(32)"))
            connection.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
        if "password_hash" in missing:
            connection.execute(text("ALTER TABLE users ADD COLUMN password_hash TEXT"))
    Base.metadata.create_all(bind=engine)
    print("Username/password schema migration complete. Existing users can claim their profile by registering with the prior display name.")


if __name__ == "__main__":
    main()
