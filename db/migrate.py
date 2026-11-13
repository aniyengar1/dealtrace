"""Apply db/migrations/*.sql to DATABASE_URL, in filename order, exactly once.

    python -m db.migrate

Tracks what's already applied in a schema_migrations table, so re-running
is always safe -- a fresh database applies everything, an already-migrated
one is a no-op. The same SQL files run unmodified against Supabase once
DATABASE_URL points there instead of local Postgres.
"""

import os
from pathlib import Path

import psycopg

from src.env import load_env

load_env()

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _ensure_tracking_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    conn.commit()


def applied_migrations(conn: psycopg.Connection) -> set[str]:
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def run(database_url: str | None = None) -> list[str]:
    """Apply every not-yet-applied migration. Returns the filenames applied."""
    database_url = database_url or os.environ["DATABASE_URL"]
    applied_now = []
    with psycopg.connect(database_url, autocommit=False) as conn:
        _ensure_tracking_table(conn)
        already = applied_migrations(conn)

        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.name in already:
                continue
            try:
                conn.execute(path.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            applied_now.append(path.name)
    return applied_now


def main() -> None:
    applied_now = run()
    if not applied_now:
        print("No new migrations to apply.")
        return
    for filename in applied_now:
        print(f"applied {filename}")


if __name__ == "__main__":
    main()
