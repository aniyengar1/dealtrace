from dataclasses import replace
from datetime import date
from decimal import Decimal
import pytest
import psycopg
from psycopg import sql
from earnings import store
from earnings.engine import hurdle, outcomes
from earnings.models import DateInterval, Policy
from earnings.__main__ import persist_calculation
from test_core import COMPANY, actual, guidance


@pytest.fixture
def company(db_conn):
    c={**COMPANY,'name':'Earnings test company'}
    store.register(db_conn,c)
    return c


def test_roundtrip_idempotency_and_edges(db_conn,company):
    facts=[actual('2026-02-01','2026-10-31','700000000'),actual('2025-02-01','2026-01-31','900000000'),actual('2025-02-01','2025-10-31','700000000')]
    g=guidance()
    for a in facts:assert store.save_actual(db_conn,a)==1
    for a in facts:assert store.save_actual(db_conn,a)==0
    assert store.save_guidance(db_conn,g)==1 and store.save_guidance(db_conn,g)==0
    a,h=store.records(db_conn,'TEST')
    assert set(x.id for x in a)==set(x.id for x in facts) and h==[g]
    r=hurdle(company,a,h,date(2026,11,11));persist_calculation(db_conn,r,a);persist_calculation(db_conn,r,a)
    loaded=store.calculation_from(db_conn.execute('SELECT payload FROM hurdle_calculations WHERE id=%s',(r.id,)).fetchone()[0])
    assert loaded==r and loaded.id==r.id
    assert db_conn.execute('SELECT count(*) FROM hurdle_input_edges WHERE calculation_id=%s',(r.id,)).fetchone()[0]==5
    assert db_conn.execute('SELECT count(*) FROM earnings_actual_edges WHERE child_id=%s',(r.inputs['prior_remaining'],)).fetchone()[0]==2
    assert db_conn.execute('SELECT growth_low FROM hurdle_calculations WHERE id=%s',(r.id,)).fetchone()[0]==Decimal('.5')
    revision=replace(facts[0],filed=date(2026,11,12),accession='amendment',value=Decimal('710000000'))
    assert store.save_actual(db_conn,revision)==1
    a,_=store.records(db_conn,'TEST');assert len(a)==4


def test_outcome_roundtrip(db_conn,company):
    g=guidance();store.save_guidance(db_conn,g)
    a=actual('2026-02-01','2027-01-31','1000000000','2027-03-20');store.save_actual(db_conn,a)
    r=outcomes(company,a,[g],cutoff=date(2027,3,20),result_issued=DateInterval.read('2027-03-10'),result_source={'accession':'a','url':'https://www.sec.gov/Archives/release','filed_date':'2027-03-10'})
    store.save_outcome(db_conn,r,a);store.save_outcome(db_conn,r,a)
    assert db_conn.execute('SELECT original_class,latest_class FROM guidance_outcomes WHERE id=%s',(r['id'],)).fetchone()==('within','within')


def test_rls_read_only_and_service_write(db_conn,company):
    cid=store.company_id('TEST')
    for role in ['anon','authenticated']:
        with db_conn.transaction():
            db_conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
            assert db_conn.execute('SELECT id FROM companies WHERE id=%s',(cid,)).fetchone()
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with db_conn.transaction():db_conn.execute('DELETE FROM companies WHERE id=%s',(cid,))
        db_conn.execute('RESET ROLE')
    with db_conn.transaction():
        db_conn.execute('SET LOCAL ROLE service_role')
        assert store.save_guidance(db_conn,guidance())==1
    db_conn.execute('RESET ROLE')


def test_constraints_cross_company_and_withdrawal(db_conn,company):
    other={**company,'ticker':'OTHER','cik':'0000000002'};store.register(db_conn,other)
    a=actual('2026-02-01','2026-10-31','700000000');store.save_actual(db_conn,a)
    r=hurdle(company,[],[],date(2026,11,11));store.save_calculation(db_conn,r)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        with db_conn.transaction():
            db_conn.execute('INSERT INTO hurdle_input_edges(calculation_id,company_id,role,actual_id) VALUES (%s,%s,%s,%s)',(r.id,store.company_id('OTHER'),'actual_ytd',a.id))


def test_registry_does_not_change_an_existing_entity(db_conn,company):
    with pytest.raises(ValueError,match='CIK cannot change'):
        store.register(db_conn,{**company,'cik':'0000000009'})
