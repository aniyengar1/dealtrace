"""Generate owner-run snapshot INSERTs from existing publication files; no DB."""
import argparse
import json
from pathlib import Path
from earnings.models import digest
ROOT=Path(__file__).resolve().parent

def script(publication_dir=ROOT, *, allow_synthetic=False):
    publication_dir=Path(publication_dir)
    rows=[('crosscheck_prediction_snapshots','predictions.json'),('crosscheck_backtest_snapshots','backtest.json')]
    statements=['-- OWNER-RUN publication copies only. Never reads or writes the live ledger.','BEGIN;']
    if allow_synthetic:
        statements[:0]=['-- SYNTHETIC SCRATCH REHEARSAL ONLY. Never publish these fabricated outcomes.']
        statements.append("DO $$ BEGIN IF current_database() NOT LIKE 'crosscheck_scoring_rehearsal_%' OR current_setting('data_directory') NOT LIKE '/tmp/crosscheck-snapshot-pg-%' THEN RAISE EXCEPTION 'Synthetic seed requires the isolated scoring-rehearsal database'; END IF; END $$;")
    for table,name in rows:
        payload=json.loads((publication_dir/name).read_text())
        if payload.get('simulation') is True and not allow_synthetic:
            raise ValueError('Synthetic outcomes cannot generate a production publication seed')
        body=json.dumps(payload,ensure_ascii=True,sort_keys=True)
        delimiter='$snapshot_'+digest(payload)[:16]+'$'
        assert delimiter not in body
        statements.append(f"INSERT INTO public.{table}(snapshot_id,payload) VALUES ('current',{delimiter}{body}{delimiter}::jsonb) ON CONFLICT(snapshot_id) DO UPDATE SET payload=EXCLUDED.payload,published_at=clock_timestamp();")
    return '\n'.join(statements+['COMMIT;',''])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input-dir',type=Path,default=ROOT);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.input_dir.resolve()!=ROOT.resolve() and not a.output:p.error('A non-default --input-dir requires an explicit --output; never overwrite the production seed implicitly')
    target=a.output or ROOT/'published_snapshot_seed.sql'
    target.write_text(script(a.input_dir));print(target)
