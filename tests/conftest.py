"""Shared pytest fixtures for DB-backed tests.

DB tests run against the real local Postgres (DATABASE_URL), not a mock --
every test gets its own transaction that's rolled back at teardown, so
nothing persists and tests never collide with data loaded by
`python -m src.load_db`. Migrations are applied once per session so the
suite is self-contained (no manual `python -m db.migrate` step required).
"""

import os

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema():
    if not os.environ.get("DATABASE_URL"):
        return
    from db.migrate import run as run_migrations

    run_migrations()


@pytest.fixture()
def db_conn():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set -- skipping DB-backed tests")
    conn = psycopg.connect(database_url, autocommit=False)
    yield conn
    conn.rollback()
    conn.close()
