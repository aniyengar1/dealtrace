"""Generate owner-run snapshot INSERTs from existing publication files; no DB."""
import argparse
import json
from pathlib import Path
from earnings.models import digest
ROOT=Path(__file__).resolve().parent

def script():
    rows=[('crosscheck_prediction_snapshots','predictions.json'),('crosscheck_backtest_snapshots','backtest.json')]
    statements=['-- OWNER-RUN publication copies only. Never reads or writes the live ledger.','BEGIN;']
    for table,name in rows:
        payload=json.loads((ROOT/name).read_text());body=json.dumps(payload,ensure_ascii=True,sort_keys=True)
        delimiter='$snapshot_'+digest(payload)[:16]+'$'
        assert delimiter not in body
        statements.append(f"INSERT INTO public.{table}(snapshot_id,payload) VALUES ('current',{delimiter}{body}{delimiter}::jsonb) ON CONFLICT(snapshot_id) DO UPDATE SET payload=EXCLUDED.payload,published_at=clock_timestamp();")
    return '\n'.join(statements+['COMMIT;',''])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'published_snapshot_seed.sql');a=p.parse_args();a.output.write_text(script());print(a.output)
