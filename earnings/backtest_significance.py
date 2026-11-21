"""Offline paired company-cluster bootstrap; never connects to a database."""
from collections import defaultdict
from decimal import Decimal, localcontext
import hashlib
import random

from .models import dumps
from .smoothed_baseline import METHOD as SMOOTHED

POOLED = 'walk-forward-pooled-base-rate'
SEED = 20261121
RESAMPLES = 10_000


def percentile(sorted_values, probability):
    """Linear interpolation at (n-1)*p, with Decimal arithmetic."""
    if not sorted_values or not Decimal(0) <= probability <= Decimal(1):
        raise ValueError('Nonempty sorted values and a probability required')
    with localcontext() as ctx:
        ctx.prec = 100
        position = Decimal(len(sorted_values)-1)*probability
        lower = int(position)
        upper = min(lower+1, len(sorted_values)-1)
        return sorted_values[lower]+(position-lower)*(sorted_values[upper]-sorted_values[lower])


def paired_company_bootstrap(rows, *, seed=SEED, resamples=RESAMPLES):
    """Resample G companies G times; retain each selected cluster's paired rows.

    Statistic is the quarter-weighted mean difference, not the unweighted mean
    of company means. Cluster sizes and resulting quarter counts can vary by
    resample. Scores/predictions are fixed, not refit within bootstrap samples.
    """
    if type(seed) is not int or type(resamples) is not int or resamples < 2:
        raise ValueError('Integer seed and at least two resamples required')
    selected = sorted((r for r in rows if r['selection']['mode']=='company'),
                      key=lambda r:(r['company'],r['id']))
    if len({r['id'] for r in selected}) != len(selected):
        raise ValueError('Duplicate prediction IDs')
    groups = defaultdict(list)
    with localcontext() as ctx:
        ctx.prec = 100
        for r in selected:
            smoothed, pooled = (Decimal(r['brier'][m]) for m in (SMOOTHED, POOLED))
            if any(not v.is_finite() or not 0 <= v <= 2 for v in (smoothed, pooled)):
                raise ValueError('Finite unscaled Brier scores in [0,2] required')
            groups[r['company']].append(smoothed-pooled)
        companies = sorted(groups)
        if len(companies) < 2:
            raise ValueError('At least two company clusters required')
        clusters = [(sum(groups[c], Decimal(0)),len(groups[c])) for c in companies]
        estimate = sum((s for s,_ in clusters),Decimal(0))/len(selected)
        rng = random.Random(seed)
        distribution = []
        draws_hash = hashlib.sha256()
        quarter_counts = []
        for _ in range(resamples):
            indices = [rng.randrange(len(companies)) for _ in companies]
            draws_hash.update((','.join(map(str,indices))+'\n').encode())
            numerator = sum((clusters[i][0] for i in indices),Decimal(0))
            denominator = sum(clusters[i][1] for i in indices)
            distribution.append(numerator/denominator)
            quarter_counts.append(denominator)
        ordered = sorted(distribution)
        low, high = (percentile(ordered,p) for p in (Decimal('0.025'),Decimal('0.975')))
    paired_inputs = [{k:r[k] for k in ('id','company')} |
                     {'smoothed_brier':r['brier'][SMOOTHED],'pooled_brier':r['brier'][POOLED]}
                     for r in selected]
    return {
        'kind':'BACKTEST_PAIRED_COMPANY_CLUSTER_BOOTSTRAP_NOT_LIVE',
        'difference':'Smoothed minus walk-forward pooled unscaled Brier',
        'n_predictions':len(selected),'n_companies':len(companies),
        'company_sizes':{c:len(groups[c]) for c in companies},
        'mean_difference':estimate,'confidence_level':'0.95',
        'interval':{'low':low,'high':high},'excludes_zero':low>0 or high<0,
        'seed':seed,'resamples':resamples,
        'rng':'Python random.Random(seed), integer randrange(G), sorted company and prediction IDs',
        'statistic':'sum of paired quarter differences / all quarters in resampled company clusters',
        'interval_method':'percentile, linear interpolation at (B-1)*p; Decimal precision100',
        'resampled_quarter_count_range':[min(quarter_counts),max(quarter_counts)],
        'paired_input_sha256':hashlib.sha256(dumps(paired_inputs).encode()).hexdigest(),
        'company_draws_sha256':draws_hash.hexdigest(),
        'bootstrap_distribution_sha256':hashlib.sha256(dumps(distribution).encode()).hexdigest(),
        'limitations':'Conditional retrospective comparison of fixed predictions on the selected company-history subset; company resampling preserves within-company pairs but not cross-company dependence from shared macro conditions or overlapping training pools. No causal or prospective generalization claim.',
    }


def sentence(result):
    interval=result['interval']
    conclusion='excludes zero in favor of Smoothed' if result['excludes_zero'] and Decimal(interval['high'])<0 else 'excludes zero against Smoothed' if result['excludes_zero'] else 'includes zero'
    return (f"On {result['n_predictions']} company-history predictions across {result['n_companies']} companies, "
            f"the paired mean Brier difference (Smoothed minus walk-forward pooled) is {Decimal(result['mean_difference']):.5f}, "
            f"with a 95% company-cluster bootstrap interval [{Decimal(interval['low']):.5f}, {Decimal(interval['high']):.5f}] "
            f"({result['resamples']:,} resamples, seed {result['seed']}), which {conclusion}, "
            "but remains a selected retrospective comparison that does not capture cross-company dependence or establish live predictive quality.")
