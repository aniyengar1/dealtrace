"""Retrospective, public-date walk-forward diagnostic; never writes live locks."""
import argparse
from datetime import date,datetime,time,timedelta,timezone
from zoneinfo import ZoneInfo
from decimal import Decimal,localcontext
from . import history,baseline
from .actuals import Blocked
from .models import dumps


def run():
    rows=history.load_all();evaluated=[];excluded=[]
    # These are today's manual reviews, explicitly NOT historical entry timestamps.
    for r in rows:r['recorded_at']=r['source_record']['outcome_basis_review']['reviewed_at']
    for r in sorted(rows,key=lambda x:(x['period_end'],x['company'])):
        if r['status']!='eligible':
            excluded.append({'id':r['id'],'company':r['company'],'reasons':r['blocking_reasons']});continue
        source=r['source_record'];release=date.fromisoformat(source['guidance_anchor_publication_date'])
        simulated=datetime.combine(release-timedelta(days=14),time.min,ZoneInfo(baseline.ZONE))
        try:b=baseline.probabilities(r['company'],rows,simulated,retrospective=True)
        except Blocked as exc:
            excluded.append({'id':r['id'],'company':r['company'],'reasons':[exc.code]});continue
        assert r['id'] not in b['historical_ids']
        evaluated.append({'id':r['id'],'company':r['company'],'period_end':r['period_end'],
            'simulated_forecast_date':simulated.isoformat(),'guidance_id':r['guidance_id'],'outcome':r['outcome'],
            'baseline':b,'brier':str(baseline.brier(b['probabilities'],r['outcome'])),
            'always_above_brier':str(baseline.brier(dict(below=Decimal(0),within=Decimal(0),above=Decimal(1)),r['outcome']))})
    with localcontext() as ctx:
        ctx.prec=80;n=len(evaluated)
        mean=lambda field: str(sum(Decimal(r[field]) for r in evaluated)/Decimal(n)) if n else None
        return {'evaluation_kind':'retrospective_reconstruction_NOT_live','executed_at':datetime.now(timezone.utc).isoformat(),
            'total_quarters':len(rows),'eligible_quarters':sum(r['status']=='eligible' for r in rows),
            'evaluated_count':n,'excluded_count':len(excluded),'mean_brier':mean('brier'),
            'always_above_mean_brier':mean('always_above_brier'),'evaluated':evaluated,'excluded':excluded,
            'limitations':['Today-curated guidance, fiscal boundaries and comparability reviews; not an operational as-recorded backtest.',
                'Only underlying SEC public-availability dates are simulated; no review timestamps are backdated.',
                'Small selected ten-company cohort; repeated overlapping histories; no calibration or predictive-quality claim.',
                'Historical report dates define the simulated horizon retrospectively; scheduled-date evidence was not reconstructed.']}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();r=run()
    with open(args.output,'x') as stream:stream.write(dumps(r)+'\n')
    print(dumps({k:v for k,v in r.items() if k not in ('evaluated','excluded')}))
