"""Replay a saved evaluation from its pinned canonical SEC document versions."""
import argparse,json,hashlib
from pathlib import Path
from . import evaluate
from .corpus import ROOT,CACHE,canonical
from earnings.sec import fetch
from earnings.models import dumps


def run(source_report,output):
    report=json.loads(Path(source_report).read_text());frozen=json.loads((ROOT/'rules_frozen_v1.json').read_text())
    for name,sha in frozen['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha:raise ValueError('Frozen extraction implementation changed: '+name)
    versions={m['source_url']:m for m in report['sources']};original=evaluate.materialize
    def pinned(doc):
        m=versions[doc['source_url']];path=Path(m['canonical_cache'])
        if path.exists():text=path.read_text()
        else:
            body,manifest=fetch(doc['source_url'])
            if manifest['sha256']!=m['raw_sha256']:raise ValueError('Original SEC source version unavailable; refusing current-version substitution')
            text=canonical(body)
        if hashlib.sha256(text.encode()).hexdigest()!=m['canonical_sha256']:raise ValueError('Pinned canonical source integrity failure')
        return text,m
    try:
        evaluate.materialize=pinned;result=evaluate.run(report['split'],output)
    finally:evaluate.materialize=original
    for field in ['strict_record','value_period_metric','fields','matches','errors']:
        if result[field]!=report[field]:raise ValueError('Replay differs: '+field)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source_report');p.add_argument('--output',required=True);a=p.parse_args();run(a.source_report,a.output)
