"""Revenue guidance rule candidates. No production-guidance loading or DB writes."""
from datetime import date,timedelta
from decimal import Decimal
import json,re,hashlib
from pathlib import Path
from earnings.models import record_id
VERSION='revenue-rules-v1'
CALENDARS=json.loads((Path(__file__).with_name('calendars.json')).read_text())
WORDS={'first':1,'second':2,'third':3,'fourth':4}
Q=re.compile(r'\b(?:Q\s*(?P<n>[1-4])\s*(?:FY|fiscal\s*(?:year\s*)?)\s*|(?P<word>first|second|third|fourth)\s+quarter\s+(?:(?:of|the|and)\s+)*(?:(?:fiscal\s*(?:year\s*)?|FY\s*))?)(?P<y>20\d{2}|\d{2})\b',re.I)
Y=re.compile(r'\b(?:full[-\s]+(?:fiscal\s+)?year(?:\s+fiscal)?|full\s+FY|fiscal\s+year|FY)\s*(20\d{2}|\d{2})\b',re.I)
LABEL=re.compile(r'\b(?:total\s+)?(?:net\s+)?revenues?\b(?:\s+guidance)?',re.I)
AMOUNT=re.compile(r'\s*(?P<dollar>\$)?\s*(?P<lo>\d[\d,]*(?:\.\d+)?)\s*(?P<u1>million|billion)?(?:\s*(?:to|[-–—])\s*\$?\s*(?P<hi>\d[\d,]*(?:\.\d+)?)\s*(?P<u2>million|billion)?)?',re.I)
DATE=re.compile(r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Sept|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+(\d{1,2}),?\s+(20\d{2})',re.I)
MONTH={v:i+1 for i,v in enumerate(['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'])}


def period(company,year,quarter=None):
    c=CALENDARS['companies'][company];ey=year+c['end_year_offset']
    if c['kind']=='months':
        start=date(ey-1,2,1);end=date(ey,1,31)
        if quarter:
            month=2+3*(quarter-1);start=date(ey-1+(month-1)//12,(month-1)%12+1,1)
            following=month+3;end=date(ey-1+(following-1)//12,(following-1)%12+1,1)-timedelta(days=1)
    else:
        def year_end(y):
            anchor=date(y,c['end_month'],c['anchor_day']);offset=(c['weekday']-anchor.weekday()+3)%7-3
            return anchor+timedelta(days=offset)
        start=year_end(ey-1)+timedelta(days=1);end=year_end(ey)
        if quarter:
            start+=timedelta(weeks=13*(quarter-1))
            if quarter<4:end=start+timedelta(weeks=13)-timedelta(days=1)
    return str(start),str(end)


def markers(text):
    qs=list(Q.finditer(text));out=[]
    for m in qs:out.append((m.start(),m.end(),int(m['y'])+(2000 if len(m['y'])==2 else 0),int(m['n']) if m['n'] else WORDS[m['word'].lower()]))
    for m in Y.finditer(text):
        if not any(q.start()<=m.start()<q.end() for q in qs):out.append((m.start(),m.end(),int(m[1])+(2000 if len(m[1])==2 else 0),None))
    return sorted(out)


def extract(text,metadata):
    candidates=[];rejected=[];issued=None
    dates=[]
    for m in DATE.finditer(text[:3500]):
        try:
            day=date(int(m[3]),MONTH[m[1][:3].lower()],int(m[2]))
            if str(day)<=metadata['filed']:dates.append(str(day))
        except ValueError:continue
    if dates:issued=max(dates)
    for label in LABEL.finditer(text):
        pre=text[max(0,label.start()-1800):label.start()];tail=text[label.end():label.end()+200]
        if re.search(r'(subscription|segment|license|ARR|services|Professionals|Consumers|growth|currency)[\s\w&]*$',pre[-55:],re.I):continue
        if not re.search(r'guidance|outlook|expects|targets|expected',pre[-350:]+label[0]+tail[:90],re.I):continue
        if re.search(r'financial highlights|results\s*[•:]|achieved|delivered|reported',pre[-180:],re.I):continue
        if re.search(r'(?:CONDENSED\s+CONSOLIDATED|These statements|Forward.Looking Statements|financial results were)',pre[-800:],re.I):continue
        # Revenue growth and reported actuals are not dollar target ranges.
        leading=re.match(r'\s*(?:(?:(?:are|is)\s+expected\s+to\s+be|to\s+be)\s*)?(?:(?:of|in\s+the\s+range\s+of|is|between|approximately)\s*)?:?\s*',tail,re.I).end()
        a=AMOUNT.match(tail,leading)
        if not a:continue
        if tail[a.end():].lstrip().startswith('%'):continue
        context=markers(pre);context=[x for x in context if len(pre)-x[1]<1100]
        if not context:
            rejected.append({'code':'UNRESOLVED_FISCAL_LABEL','start':label.start()});continue
        short=list(re.finditer(r'\b(first|second|third|fourth)\s+quarter\b',pre[-160:],re.I))
        if short:
            sm=short[-1];position=len(pre)-len(pre[-160:])+sm.start()
            if position>context[-1][1]:context.append((position,position+len(sm[0]),context[-1][2],WORDS[sm[1].lower()]))
        annual=list(re.finditer(r'\bfull\s+(?:fiscal\s+)?year\b',pre[-160:],re.I))
        if annual:
            am=annual[-1];position=len(pre)-len(pre[-160:])+am.start()
            if position>context[-1][1]:context.append((position,position+len(am[0]),context[-1][2],None))
        # Adjacent heading columns: Qx FYyyyy Guidance / FYyyyy Guidance.
        chosen=context[-2:] if len(context)>=2 and re.fullmatch(r'[\s\w:()\-]*',pre[context[-2][1]:context[-1][0]]) and context[-2][3] is not None and context[-1][3] is None and len(pre)-context[-2][0]<250 else context[-1:]
        amounts=[];pos=leading
        for column in range(len(chosen)):
            match=AMOUNT.match(tail,pos)
            if not match:break
            u=(match['u2'] or match['u1'] or '').lower()
            scale={'million':Decimal(1000000),'billion':Decimal(1000000000)}.get(u)
            if scale is None and re.search(r'in\s+millions',pre[-1000:],re.I):scale=Decimal(1000000)
            if scale is None or (not match['dollar'] and not u):
                rejected.append({'code':'UNRESOLVED_UNIT','start':label.start()});break
            scale_low={'million':Decimal(1000000),'billion':Decimal(1000000000)}.get((match['u1'] or '').lower(),scale)
            low=Decimal(match['lo'].replace(',',''))*scale_low;high=Decimal((match['hi'] or match['lo']).replace(',',''))*scale
            if low>high:rejected.append({'code':'INVALID_RANGE','start':label.start()});break
            amounts.append((low,high,match.end()));pos=match.end()
        for target,amount in zip(chosen,amounts):
            year,q=target[2:];low,high,endpos=amount
            try:start,end=period(metadata['company'],year,q)
            except (ValueError,KeyError):continue
            begin=max(0,label.start()-len(pre)+target[0]);finish=label.end()+endpos;quote=text[begin:finish]
            if not issued:rejected.append({'code':'UNRESOLVED_ISSUANCE_DATE','start':begin});continue
            # Unqualified issuer total revenue; reject explicit adjusted/segment scope.
            if re.search(r'(?:non.GAAP|adjusted|organic|constant.currency)\s+(?:total\s+)?revenue',quote,re.I):continue
            c={**{k:metadata[k] for k in ['company','accession','exhibit','source_url']},'issued':{'start':issued,'end':issued,'precision':'day'},'filed':metadata['filed'],
              'start':start,'end':end,'low':str(low),'high':str(high),'unit':'USD','basis':'US_GAAP_consolidated_reported',
              'metric':'quarterly_consolidated_revenue' if q else 'consolidated_revenue','status':'initial','original_verified':False,
              'quote':quote,'quote_start':begin,'quote_end':finish,'fiscal_label':f'Q{q} FY{year}' if q else f'FY{year}',
              'method_version':VERSION,'source_sha256':metadata.get('raw_sha256'),'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),
              'calendar_policy':CALENDARS['version'],'review_required':True,'notes':'Candidate only. Unqualified issuer revenue interpreted as consolidated reported USD; registered fiscal calendar is manual metadata. No automatic production writes.'}
            c['id']=record_id('extracted-guidance-candidate-v1',c);candidates.append(c)
    # Same target/range repeated in headline and outlook table is one candidate.
    unique={}
    for c in candidates:unique.setdefault((c['metric'],c['start'],c['end'],Decimal(c['low']),Decimal(c['high'])),c)
    return list(unique.values()),rejected


def references(text,metadata,prior):
    """Explicit reaffirmations may reference only earlier extracted candidates."""
    result=[]
    dates=[]
    for d in DATE.finditer(text[:3500]):
        value=str(date(int(d[3]),MONTH[d[1][:3].lower()],int(d[2])))
        if value<=metadata['filed']:dates.append(value)
    if not dates:return []
    for m in re.finditer(r'\breaffirm\w*|\bno anticipated change\b',text,re.I):
        end=min(len(text),m.start()+550);sentence=re.search(r'\.[”"\']?\s',text[m.end():end])
        if sentence:end=m.end()+sentence.start()+1
        quote=text[m.start():end]
        clause=re.split(r'previously provided|as provided|provided in|that was|as disclosed',quote,flags=re.I)[0]
        found=markers(clause);years={x[2] for x in found}
        if not years:
            end_date=re.search(r'fiscal year ending\s+('+DATE.pattern+r')',clause,re.I)
            if end_date:
                dm=DATE.search(end_date[0]);years={int(dm[3])-CALENDARS['companies'][metadata['company']]['end_year_offset']}
        qs={int(q) for q in re.findall(r'\bQ\s*([1-4])\b',clause,re.I)}
        qs|={WORDS[q.lower()] for q in re.findall(r'\b(first|second|third|fourth)\s+quarter',clause,re.I)}
        targets={(x[2],x[3]) for x in found}
        for y in years:
            targets|={(y,q) for q in qs}
            if re.search(r'full|fiscal year|FY',clause,re.I):targets.add((y,None))
        for y,q in targets:
            start,finish=period(metadata['company'],y,q);metric='quarterly_consolidated_revenue' if q else 'consolidated_revenue'
            old=prior.get((metadata['company'],metric,start,finish))
            if not old or old['filed']>metadata['filed']:continue
            c={**old,**{k:metadata[k] for k in ['company','accession','exhibit','source_url']},'issued':{'start':max(dates),'end':max(dates),'precision':'day'},'filed':metadata['filed'],
                'status':'reaffirmed','quote':quote,'quote_start':m.start(),'quote_end':end,'source_sha256':metadata.get('raw_sha256'),
                'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),'carried_from_candidate_id':old['id'],
                'notes':'Explicit reaffirmation; amounts carried only from an earlier extracted candidate, not manual gold or production guidance. Review required.'}
            c.pop('id',None);c['id']=record_id('referenced-guidance-candidate-v1',c);result.append(c)
    return result
