"""Publication SQL tests never use DATABASE_URL or the live ledger."""
import json
import os
from pathlib import Path
import psycopg
import pytest
from earnings.publication.snapshot_sql import script
ROOT=Path(__file__).resolve().parents[2]


def test_seed_only_writes_the_two_publication_tables():
    sql=script()
    assert sql.count('INSERT INTO public.')==2
    assert 'earnings_live_' not in sql and 'guidance_versions' not in sql
    assert 'crosscheck_prediction_snapshots' in sql and 'crosscheck_backtest_snapshots' in sql
    assert sql.startswith('-- OWNER-RUN') and sql.endswith('COMMIT;\n')


def test_ddl_has_no_live_views_and_revokes_truncate_beyond_rls():
    sql=(ROOT/'earnings/sql/published_snapshots.sql').read_text()
    assert 'CREATE VIEW' not in sql and 'REFERENCES' not in sql
    assert sql.count('FORCE ROW LEVEL SECURITY')==2
    assert "'anon','authenticated','service_role'" in sql
    assert 'GRANT SELECT ON' in sql and 'BYPASSRLS role' in sql


def test_roles_against_isolated_scratch_database():
    dsn=os.environ.get('CROSSCHECK_SCRATCH_DATABASE_URL')
    if not dsn:pytest.skip('Dedicated scratch PostgreSQL not configured; never use live DATABASE_URL')
    with psycopg.connect(dsn,autocommit=True) as c:
        assert c.execute('SHOW data_directory').fetchone()[0].startswith('/tmp/crosscheck-snapshot-pg-')
        ddl=(ROOT/'earnings/sql/published_snapshots.sql').read_text()
        c.execute(ddl);c.execute(script())
        c.execute("DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF; END $$")
        c.execute('GRANT ALL ON crosscheck_prediction_snapshots,crosscheck_backtest_snapshots TO anon')
        c.execute(ddl) # revoke even pre-existing/default Supabase grants
        assert not c.execute("SELECT has_table_privilege('anon','crosscheck_prediction_snapshots','TRUNCATE')").fetchone()[0]
        with c.transaction():
            c.execute('SET LOCAL ROLE dealtrace_web')
            assert int(c.execute("SELECT payload->>'prediction_count' FROM crosscheck_prediction_snapshots").fetchone()[0])==8
        for table in ['crosscheck_prediction_snapshots','crosscheck_backtest_snapshots']:
            for query in [f'DELETE FROM {table}',f'TRUNCATE {table}',f'UPDATE {table} SET published_at=clock_timestamp()',f"INSERT INTO {table} SELECT * FROM {table}"]:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with c.transaction():c.execute('SET LOCAL ROLE dealtrace_web');c.execute(query)
