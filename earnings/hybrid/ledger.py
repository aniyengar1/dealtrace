"""Atomic earnings-only accounting. Nanodollars and integer tokens; no floats.

A reserve is retained on crash/unknown usage. At most two active attempts across
processes. This is a local budget coordinator, not a Cloud billing cap, and cannot
protect against an operator changing this code/database or provider misbilling.
"""
import json,sqlite3,uuid
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
CEILING=8_000_000_000
INPUT_NANO=1500
OUTPUT_NANO=7500

def now():return datetime.now(timezone.utc)
def cost(input_tokens,output_tokens):
    if any(type(x) is not int or x<0 for x in (input_tokens,output_tokens)):raise ValueError('Nonnegative integer tokens required')
    return input_tokens*INPUT_NANO+output_tokens*OUTPUT_NANO

def usd(nano):return str(Decimal(nano)/Decimal(1_000_000_000))

def known_subtotal(usage):
    if not usage:return None
    fields=[(usage.get('prompt_token_count'),INPUT_NANO),(usage.get('candidates_token_count'),OUTPUT_NANO),(usage.get('thoughts_token_count'),OUTPUT_NANO)]
    known=[v*rate for v,rate in fields if type(v) is int and v>=0]
    return sum(known) if known else None

class Gate(ValueError):pass

class Ledger:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS attempts(
              id TEXT PRIMARY KEY,item TEXT NOT NULL,attempt INTEGER NOT NULL,
              created_at TEXT NOT NULL,state TEXT NOT NULL,reserved_nano INTEGER NOT NULL CHECK(reserved_nano>=0),
              held_nano INTEGER NOT NULL CHECK(held_nano>=0),active INTEGER NOT NULL CHECK(active IN(0,1)),
              input_tokens INTEGER,candidate_tokens INTEGER,thinking_tokens INTEGER,other_tokens INTEGER,
              accounted_nano INTEGER,metadata TEXT NOT NULL,UNIQUE(item,attempt));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT NOT NULL,attempt_id TEXT,kind TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS halt(reason TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
            CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append-only events'); END;
            ''')
    def connect(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return c
    def event(self,c,aid,kind,payload):c.execute('INSERT INTO events(at,attempt_id,kind,payload) VALUES(?,?,?,?)',(now().isoformat(),aid,kind,json.dumps(payload,sort_keys=True)))
    def reserve(self,item,config,metadata,clock=None):
        clock=clock or now();deadline=datetime.fromisoformat(config['deadline'])
        revised=config.get('reservation_policy')=='owner_approved_requested_output_estimate_v4'
        operational=revised or config.get('reservation_policy')=='owner_approved_conservative_estimate_not_provider_cap'
        if operational:
            counted=metadata.get('counted_input_tokens')
            if type(counted) is not int or counted<=0:raise Gate('PROVIDER_INPUT_COUNT_REQUIRED')
            max_input=counted if revised else counted+config['input_reservation_margin_tokens']
            max_output=(config['max_output_tokens'] if revised else config['max_generated_tokens_documented'])*config['output_reservation_multiplier']
            # Owner-approved estimate, NOT a documented maximum. Round up cents.
            cents=10_000_000
            maximum=cost(max_input,max_output) if revised else max(1_000_000_000,((cost(max_input,max_output)+cents-1)//cents)*cents)
        else:
            if not config.get('billable_thinking_bound_verified'):raise Gate('UNVERIFIED_BILLABLE_THINKING_BOUND')
            max_input=config.get('max_input_tokens_documented');max_output=config.get('max_billable_output_tokens')
            if not isinstance(max_input,int) or not isinstance(max_output,int):raise Gate('MISSING_SAFE_TOKEN_BOUNDS')
            maximum=cost(max_input,max_output)
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM halt').fetchone():raise Gate('EXPERIMENT_HALTED')
            count=c.execute('SELECT count(*) FROM attempts WHERE item=?',(item,)).fetchone()[0]
            limit=1 if revised or metadata.get('is_probe') else 3
            if count>=limit:raise Gate('RETRIES_EXHAUSTED')
            remaining=limit-count;allowance=(600 if operational else 300)*remaining+sum(config['retry_backoff_seconds'][count:limit-1])+5
            if clock+timedelta(seconds=allowance)>=deadline:raise Gate('DEADLINE_RETRY_ALLOWANCE')
            if c.execute('SELECT 1 FROM attempts WHERE item=? AND active=1',(item,)).fetchone():raise Gate('ITEM_ALREADY_IN_FLIGHT')
            if c.execute('SELECT count(*) FROM attempts WHERE active=1').fetchone()[0]>=2:raise Gate('CONCURRENCY_LIMIT')
            held=c.execute('SELECT coalesce(sum(held_nano),0) FROM attempts').fetchone()[0]
            if held+maximum>CEILING:raise Gate('BUDGET_LIMIT')
            aid=str(uuid.uuid4());c.execute('INSERT INTO attempts(id,item,attempt,created_at,state,reserved_nano,held_nano,active,metadata) VALUES(?,?,?,?,?,?,?,?,?)',(aid,item,count+1,clock.isoformat(),'reserved',maximum,maximum,1,json.dumps(metadata,sort_keys=True)))
            self.event(c,aid,'reserved',{'reservation_nano':maximum,'input_estimate':max_input,'output_including_thinking_allowance_estimate':max_output,'provider_billing_cap_guaranteed':False,'metadata':metadata});return aid
    def finish(self,aid,usage=None,*,state='response',metadata=None):
        # Cached tokens are a subset of prompt tokens, not additional input.
        # Candidates and thoughts are disjoint SDK counters; never add total
        # token count to them. Missing/contradictory usage holds full reservation.
        keys=('prompt_token_count','candidates_token_count','thoughts_token_count','total_token_count')
        known=bool(usage) and all(type(usage.get(k)) is int and usage[k]>=0 for k in keys)
        other=usage.get('tool_use_prompt_token_count') if usage else None
        if other is None:other=0 # No tools, grounding, media or cache creation enabled.
        known=known and type(other) is int and other==0
        if known:known=usage['total_token_count']==sum(usage[k] for k in keys[:3])+other
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM attempts WHERE id=?',(aid,)).fetchone()
            if not row or not row['active']:raise Gate('ATTEMPT_NOT_ACTIVE')
            if type(other) is int and other>0:c.execute('INSERT INTO halt(reason) VALUES(?)',('UNEXPECTED_OTHER_BILLABLE_USAGE',))
            accounted=cost(usage['prompt_token_count'],usage['candidates_token_count']+usage['thoughts_token_count']) if known else None
            subtotal=known_subtotal(usage)
            held=accounted if known else max(row['reserved_nano'],subtotal or 0)
            if not known and subtotal is not None and subtotal>row['reserved_nano']:
                c.execute('INSERT INTO halt(reason) VALUES(?)',('KNOWN_SUBTOTAL_EXCEEDS_RESERVATION',))
            if known and accounted>row['reserved_nano']:
                c.execute('INSERT INTO halt(reason) VALUES(?)',('PROVIDER_USAGE_EXCEEDED_RESERVED_BOUND',));state='bound_breach'
            if known and accounted>500_000_000:c.execute('INSERT INTO halt(reason) VALUES(?)',('INDIVIDUAL_ATTEMPT_EXCEEDS_050_USD',))
            c.execute('UPDATE attempts SET state=?,held_nano=?,active=0,input_tokens=?,candidate_tokens=?,thinking_tokens=?,other_tokens=?,accounted_nano=? WHERE id=?',(state if known else 'unknown_usage_'+state,held,usage.get(keys[0]) if usage else None,usage.get(keys[1]) if usage else None,usage.get(keys[2]) if usage else None,other,accounted,aid))
            self.event(c,aid,'finished',{'state':state,'usage':usage,'usage_known':known,'known_counter_subtotal_nano_not_extra_charge':subtotal,'held_nano':held,'metadata':metadata})
    def summary(self):
        with self.connect() as c:
            rows=[dict(r) for r in c.execute('SELECT * FROM attempts ORDER BY created_at,id')]
            for r in rows:
                r['known_counter_subtotal_nano_not_extra_charge']=known_subtotal({'prompt_token_count':r['input_tokens'],'candidates_token_count':r['candidate_tokens'],'thoughts_token_count':r['thinking_tokens']})
            return {'headroom_usd':usd(CEILING-sum(r['held_nano'] for r in rows)),'known_counter_subtotals_usd_not_extra_charges':usd(sum(r['known_counter_subtotal_nano_not_extra_charge'] or 0 for r in rows)),'ceiling_usd':usd(CEILING),'attempts':len(rows),'known_accounted_usd':usd(sum(r['accounted_nano'] for r in rows if r['accounted_nano'] is not None)),'outstanding_unknown_or_active_reservations_usd':usd(sum(r['held_nano'] for r in rows if r['accounted_nano'] is None)),'total_held_usd':usd(sum(r['held_nano'] for r in rows)),'active_attempts':sum(r['active'] for r in rows),'halted':bool(c.execute('SELECT 1 FROM halt').fetchone()),'records':rows}
