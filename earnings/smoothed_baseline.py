"""Fixed add-one comparison, sharing the original empirical input selection."""
from copy import deepcopy
from decimal import Decimal,localcontext,ROUND_HALF_EVEN
from .baseline import LABELS,probabilities as empirical
METHOD='quarter-frequency-laplace-v1'

def rates(counts):
    if set(counts)!=set(LABELS) or any(type(v) is not int or v<0 for v in counts.values()):
        raise ValueError('Nonnegative integer counts for all three classes required')
    with localcontext() as ctx:
        ctx.prec=80
        denominator=Decimal(sum(counts.values())+3)
        below=((Decimal(counts['below'])+1)/denominator).quantize(Decimal('1e-24'),rounding=ROUND_HALF_EVEN)
        within=((Decimal(counts['within'])+1)/denominator).quantize(Decimal('1e-24'),rounding=ROUND_HALF_EVEN)
        return dict(zip(LABELS,(below,within,Decimal(1)-below-within)))

def from_empirical(original):
    result=deepcopy(original)
    result.update(method_version=METHOD,probabilities=rates(original['counts']))
    result['policy']['smoothing']='fixed Dirichlet(1,1,1) / add-one Laplace; no fitting'
    result['policy']['prior_counts']={label:1 for label in LABELS}
    result['limitations'].append('Fixed symmetric prior shrinks extreme sample rates; it is not calibrated or tuned to future outcomes.')
    return result

def probabilities(company,rows,prediction_time,*,retrospective=False):
    return from_empirical(empirical(company,rows,prediction_time,retrospective=retrospective))
