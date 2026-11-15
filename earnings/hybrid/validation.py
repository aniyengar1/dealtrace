"""Deterministic checks, never a guarantee of semantic correctness."""
import re
from decimal import Decimal,InvalidOperation
from datetime import date
from earnings.models import record_id
from .schema import Extraction
from .evidence import locate,roles as evidence_roles
STATUS_ERRORS={'UNRESOLVED_STATUS','INITIAL_NOT_ESTABLISHED','MISSING_STATUS_EVIDENCE','MISSING_STATUS_REFERENCE','FUTURE_OR_SAME_RELEASE_STATUS_REFERENCE','INCOMPARABLE_STATUS_REFERENCE','STATUS_ARITHMETIC_MISMATCH','STATUS_AMOUNTS_UNRESOLVED','INVALID_STATUS_REFERENCE_INPUT','STATUS_REFERENCE_REQUIRED'}
REQUIRED={'metric','scope','period','units','basis','guidance_type','amount','issuance'}

def number(m):
    if not m:return None
    if not re.fullmatch(r'\$?\s*\d[\d,]*(?:\.\d+)?',m.value):raise ValueError('Not an explicit absolute monetary literal')
    return Decimal(m.value.replace('$','').replace(',','').strip())*Decimal(m.scale)

def validate(payload,documents,calendar):
    parsed=Extraction.model_validate(payload);docs={d['source_id']:d for d in documents};out=[]
    for i,o in enumerate(parsed.observations):
        errors=[];notes=['SEMANTIC_HUMAN_REVIEW_REQUIRED'];src=docs.get(o.source_id)
        if not src:errors.append('UNKNOWN_SOURCE')
        roles=set();locations=[];valid=[]
        for span in o.evidence:
            location=locate(span,docs.get(span.source_id));locations.append(location)
            if location['status']!='UNIQUE_EXACT_MATCH':errors.append(location['status'])
            else:
                valid.append(span)
                if not location['original_offsets_match'] and span.start is not None:
                    notes.append('MODEL_OFFSETS_DIFFER_DETERMINISTIC_LOCATION_PROPOSED')
                if span.source_id==o.source_id:roles.update(evidence_roles(span))
        if not REQUIRED.issubset(roles):errors.append('INCOMPLETE_EVIDENCE_ROLES')
        if o.table_id:
            if not src or o.table_id not in {t['id'] for t in src['tables']}:errors.append('UNKNOWN_TABLE')
            elif not any('table_header' in evidence_roles(s) and s.quote in next(t['text'] for t in src['tables'] if t['id']==o.table_id) for s in valid):errors.append('MISSING_MATCHING_TABLE_HEADER')
            if not o.column_label or o.table_row_index is None or o.table_column_index is None:errors.append('MISSING_COLUMN_IDENTITY')
            elif o.table_row_index<0 or o.table_column_index<0:errors.append('INVALID_TABLE_COORDINATE')
            else:
                table=next((t for t in src['tables'] if t['id']==o.table_id),None) if src else None
                if table and (o.table_row_index>=len(table['rows']) or o.table_column_index>=len(table['rows'][o.table_row_index])):errors.append('INVALID_TABLE_COORDINATE')
        if o.scope_support!='explicit':notes.append('SCOPE_INFERRED_OR_UNRESOLVED')
        eligible=o.metric_class in ('consolidated_revenue','net_sales') and o.scope=='consolidated' and o.guidance_type=='direct' and o.basis_kind=='reported'
        if not eligible:errors.append('NONELIGIBLE_OR_AMBIGUOUS_INTERPRETATION')
        if o.currency!='USD':errors.append('UNRESOLVED_CURRENCY')
        lo=hi=None
        try:
            if o.amount_style=='range':lo,hi=number(o.low),number(o.high)
            elif o.amount_style=='point':lo=hi=number(o.low)
            elif o.amount_style=='absolute_tolerance':
                b,t=number(o.center),number(o.tolerance)
                if b is None or t is None:raise ValueError('Missing base/tolerance')
                lo,hi=b-t,b+t
            elif o.status!='withdrawn':errors.append('NON_ABSOLUTE_OR_MISSING_AMOUNT')
            if o.status=='withdrawn':
                if any(x is not None for x in (o.low,o.high,o.center,o.tolerance)):errors.append('WITHDRAWAL_HAS_AMOUNTS')
                lo=hi=None
            elif lo is None or hi is None:errors.append('MISSING_AMOUNT')
            elif lo>hi:errors.append('REVERSED_BOUNDS')
        except (InvalidOperation,ValueError):errors.append('INVALID_LITERAL_OR_TOLERANCE')
        amount_quotes=' '.join(s.quote for s in valid if 'amount' in evidence_roles(s) and s.source_id==o.source_id)
        unit_quotes=' '.join(s.quote for s in valid if evidence_roles(s)&{'amount','units','table_header'} and s.source_id==o.source_id)
        for m in (o.low,o.high,o.center,o.tolerance):
            if m:
                literal=m.value.replace('$','').strip()
                if not re.search(r'(?<![\d.,])'+re.escape(literal)+r'(?![\d.,])',amount_quotes):errors.append('NUMBER_NOT_IN_AMOUNT_EVIDENCE')
                unit={'1000':'thousand','1000000':'million','1000000000':'billion'}.get(m.scale)
                if unit and unit not in unit_quotes.lower():errors.append('SCALE_NOT_SUPPORTED')
        if '$' not in unit_quotes and 'USD' not in unit_quotes:errors.append('CURRENCY_NOT_SUPPORTED')
        resolved_start,resolved_end=o.period_start,o.period_end
        try:
            if o.fiscal_year is None or o.fiscal_quarter not in (None,1,2,3,4):raise ValueError()
            expected=calendar(o.fiscal_year,o.fiscal_quarter)
            if any(given is not None and given!=bound for given,bound in zip((o.period_start,o.period_end),expected)):
                errors.append('CALENDAR_BOUNDARY_MISMATCH')
            else:
                resolved_start,resolved_end=expected
                if o.period_start is None or o.period_end is None:notes.append('PERIOD_RESOLVED_FROM_REGISTERED_CALENDAR_NOT_MODEL')
        except (ValueError,KeyError):errors.append('UNRESOLVED_FISCAL_CALENDAR')
        try:
            issued1=date.fromisoformat(o.issued_start);issued2=date.fromisoformat(o.issued_end)
            if issued1>issued2 or not src or str(issued2)>src['filed']:errors.append('INVALID_PUBLIC_AVAILABILITY')
            # Literal date support requires a separate review; offsets cannot
            # prove that an arbitrary cited date is this target's issue date.
            notes.append('ISSUANCE_SEMANTICS_REQUIRE_REVIEW')
        except (ValueError,TypeError):errors.append('UNRESOLVED_ISSUANCE')
        if o.status=='unresolved':errors.append('UNRESOLVED_STATUS')
        if o.status_support=='prior_range':
            j=o.prior_observation_index
            if j is None or j<0 or j>=len(parsed.observations) or j==i:errors.append('MISSING_STATUS_REFERENCE')
            else:
                prior=parsed.observations[j];pd=docs.get(prior.source_id)
                if not pd or not src or pd['filed']>=src['filed'] or prior.source_id==o.source_id:errors.append('FUTURE_OR_SAME_RELEASE_STATUS_REFERENCE')
                key=lambda x:(x.metric_class,x.scope,x.basis_kind,tuple(x.scope_qualifiers),x.currency,x.fiscal_year,x.fiscal_quarter,x.guidance_type)
                if key(o)!=key(prior) or prior.guidance_type!='direct' or (pd and src and pd.get('company')!=src.get('company')):errors.append('INCOMPARABLE_STATUS_REFERENCE')
                try:
                    def endpoints(x):
                        if x.amount_style=='point':return number(x.low),number(x.low)
                        if x.amount_style=='range':return number(x.low),number(x.high)
                        if x.amount_style=='absolute_tolerance':return number(x.center)-number(x.tolerance),number(x.center)+number(x.tolerance)
                        raise ValueError()
                    before=endpoints(prior);after=(lo,hi)
                    if None in before+after:raise ValueError()
                    status='reaffirmed' if before==after else 'raised' if after[0]>=before[0] and after[1]>=before[1] else 'lowered' if after[0]<=before[0] and after[1]<=before[1] else 'unresolved'
                    if o.status!=status:errors.append('STATUS_ARITHMETIC_MISMATCH')
                except (ValueError,TypeError,InvalidOperation):errors.append('STATUS_AMOUNTS_UNRESOLVED')
        elif o.status=='initial':
            if o.status_support!='explicit_issuance':errors.append('INITIAL_NOT_ESTABLISHED')
        elif o.status not in ('withdrawn','unresolved'):errors.append('STATUS_REFERENCE_REQUIRED')
        if o.status!='unresolved' and 'status' not in roles:errors.append('MISSING_STATUS_EVIDENCE')
        result={'evidence_locations':locations,'index':i,'proposal':o.model_dump(),'resolved_period_start':resolved_start,'resolved_period_end':resolved_end,'normalized_low':str(lo) if lo is not None else None,'normalized_high':str(hi) if hi is not None else None,'normalization':'USD center-/+USD tolerance; endpoints not verbatim' if o.amount_style=='absolute_tolerance' else 'Decimal explicit literals','deterministic_errors':sorted(set(errors)),'review_flags':notes,'semantic_validation':'NOT_GUARANTEED','quarantined':True,'review_status':'human_review_pending','deterministic_checks_passed':not errors}
        result['id']=record_id('hybrid-post-diagnostic-validator-repair-v1',result);out.append(result)
    # Status history is separate from validity of a quoted range as evidence.
    # All metric/scope/source/unit/basis/period/availability checks remain required.
    for result in out:
        result['range_evidence_errors']=sorted(set(result['deterministic_errors'])-STATUS_ERRORS)
        if result['proposal']['status']=='withdrawn' or result['normalized_low'] is None or result['normalized_high'] is None:
            result['range_evidence_errors']=sorted(set(result['range_evidence_errors']+['RANGE_WITHDRAWN_OR_MISSING']))
        result['range_evidence_checks_passed']=not result['range_evidence_errors']
    # An unsupported range still cannot support a revision; its own unknown
    # revision label alone does not invalidate otherwise supported amounts.
    for result in out:
        j=result['proposal']['prior_observation_index']
        if j is not None and 0<=j<len(out) and not out[j]['range_evidence_checks_passed']:
            result['deterministic_errors']=sorted(set(result['deterministic_errors']+['INVALID_STATUS_REFERENCE_INPUT']));result['deterministic_checks_passed']=False
    for result in out:
        result['resolved_status']='unresolved' if result['deterministic_errors'] else result['proposal']['status']
    return {'validation_version':'post-diagnostic-validator-repair-v1','observations':out,'unresolved_sections':parsed.unresolved_sections,'human_review_complete':False}
