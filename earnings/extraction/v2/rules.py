"""Structured revenue rows and explicit prose contexts; no gold or DB access."""
import re,hashlib
from decimal import Decimal
from datetime import date
from bs4 import BeautifulSoup
from earnings.models import record_id
from earnings.extraction.corpus import canonical
from earnings.extraction.rules import period,markers,DATE,MONTH,AMOUNT,CALENDARS
VERSION='revenue-rules-v2'
REVENUE=re.compile(r'^(?:(?:total|net|consolidated)\s+)?revenues?\b',re.I)
INELIGIBLE=re.compile(r'\b(?:annual\s+recurring|ARR|subscription|segment|organic|constant.currency|adjusted|services|license)\b',re.I)
LEAD=re.compile(r'\s*(?:(?:guidance|now|will|would|is|are|expected|expects|to|be|in|the|range|of|between|approximately)\b[\s:]*)*',re.I)


def frames(text):
    out=[];previous_end=0
    for a,b,y,q in markers(text):
        out.append({'a':a,'b':b,'year':y,'quarter':q,'direct':not re.search(r'implied|derived|estimated|calculated',text[max(previous_end,a-40):a],re.I),'header':text[a:b]})
        previous_end=b
    # Bare year is permitted only in explicit issuer outlook prose, never a
    # number inherited across paragraphs or from an unrelated prior quarter.
    for m in re.finditer(r'\bFor\s+(20\d{2})\s*[,;:]',text,re.I):
        out.append({'a':m.start(),'b':m.end(),'year':int(m[1]),'quarter':None,'direct':True,'header':m[0]})
    return sorted(out,key=lambda f:(f['a'],f['b']))


def issuance(text,metadata):
    options=[]
    for source_name,source in [('exhibit',text),('primary',metadata.get('primary_text',''))]:
        for m in DATE.finditer(source):
            value=str(date(int(m[3]),MONTH[m[1][:3].lower()],int(m[2])))
            if value>metadata['filed']:continue
            pre=source[max(0,m.start()-100):m.start()];post=source[m.end():m.end()+220]
            dateline=bool(re.search(r'(?:--|[–—-]|NEW YORK,|SAN FRANCISCO,|AUSTIN,|SAN JOSE,)\s*$',pre))
            on_event=bool(re.search(r'\bOn\s*$',pre,re.I) and re.search(r'announc|reaffirm|guidance|press release',post,re.I))
            asof=bool(re.search(r'as of today,?\s*$',pre,re.I))
            if dateline or on_event or asof:
                options.append((value,source_name,m.start(),m.end(),m[0]))
    if not options:return None
    newest=max(v[0] for v in options);same=[v for v in options if v[0]==newest];v=sorted(same,key=lambda v:(v[1]!='exhibit',v[2]))[0]
    return {'start':v[0],'end':v[0],'precision':'day','evidence_source':v[1],'evidence_quote':v[4],'evidence_start':v[2],'evidence_end':v[3]}


def money_matches(text,header):
    values=[];pos=0
    while pos<len(text):
        pos=LEAD.match(text,pos).end();m=AMOUNT.match(text,pos)
        if not m:break
        if text[m.end():].lstrip().startswith('%'):return [],'GROWTH_ONLY'
        u1=(m['u1'] or m['u2'] or '').lower();u2=(m['u2'] or m['u1'] or '').lower()
        scales={'million':Decimal(1000000),'billion':Decimal(1000000000)}
        s1=scales.get(u1);s2=scales.get(u2)
        if s1 is None and re.search(r'in\s+millions',header,re.I):s1=s2=Decimal(1000000)
        if s1 is None or s2 is None or (not m['dollar'] and not u1):return [],'UNRESOLVED_UNIT'
        lo=Decimal(m['lo'].replace(',',''))*s1;hi=Decimal((m['hi'] or m['lo']).replace(',',''))*s2
        if lo>hi:return [],'INVALID_RANGE'
        values.append({'low':lo,'high':hi,'a':m.start(),'b':m.end()});pos=m.end()
        # Adjacent table columns contain no explanatory words between values.
        if not re.match(r'\s*\$',text[pos:]):break
    return values,None


def extract(body,metadata):
    text=canonical(body);soup=BeautifulSoup(body,'html.parser');observations=[];abstentions=[];day=issuance(text,metadata)
    def reject(code,quote,a=None,**extra):
        abstentions.append({'code':code,'quote':quote,'source_url':metadata['source_url'],'quote_start':a,**extra})
    def emit(frame,amount,quote,a,context,origin):
        if not frame['direct']:reject('IMPLIED_OR_DERIVED_TARGET',quote,a,fiscal_label=frame['header']);return
        if day is None:reject('UNRESOLVED_ISSUANCE_DATE',quote,a);return
        try:start,end=period(metadata['company'],frame['year'],frame['quarter'])
        except (KeyError,ValueError):reject('UNRESOLVED_PERIOD',quote,a);return
        if a<0 or text[a:a+len(quote)]!=quote:reject('OFFSET_NOT_EXACT',quote,a);return
        c={**{k:metadata[k] for k in ['company','source_url','accession','exhibit','filed']},'issued':{k:day[k] for k in ['start','end','precision']},
           'issuance_evidence':day,'metric':'quarterly_consolidated_revenue' if frame['quarter'] else 'consolidated_revenue',
           'start':start,'end':end,'low':str(amount['low']),'high':str(amount['high']),'unit':'USD','basis':'US_GAAP_consolidated_reported',
           'status':None,'original_verified':False,'fiscal_label':f'Q{frame["quarter"]} FY{frame["year"]}' if frame['quarter'] else f'FY{frame["year"]}',
           'quote':quote,'quote_start':a,'quote_end':a+len(quote),'context':context,'origin':origin,'direct_guidance':True,
           'source_sha256':metadata.get('raw_sha256'),'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),
           'method_version':VERSION,'calendar_policy':CALENDARS['version'],'review_required':True}
        c['id']=record_id('v2-revenue-observation',c);observations.append(c)
    for row in soup.find_all('tr'):
        if row.find('table'):continue
        rowtext=canonical(str(row).encode());label=REVENUE.match(rowtext)
        if not label:
            if re.match(r'^(?:annual recurring revenue|ARR|subscription revenue|segment revenue)\b',rowtext,re.I):reject('NON_CONSOLIDATED_METRIC',rowtext)
            continue
        if re.match(r'\s*(?:growth|adjusted|in constant)',rowtext[label.end():],re.I):continue
        table=row.find_parent('table')
        if table is None:continue
        tabletext=canonical(str(table).encode());local=tabletext.find(rowtext);header=tabletext[:local]
        if re.search(r'(?:months?|years?) ended',header,re.I):continue
        table_start=text.find(tabletext);external=text[max(0,table_start-800):table_start]
        fs=frames(header)
        if not fs:fs=frames(external)[-1:]
        if not fs or not re.search(r'guidance|outlook|targets|expects',header+' '+external,re.I):continue
        # Repeated heading sections: retain the last complete header row, not
        # the latest token after concatenating multiple unrelated metric rows.
        prior_rows=[]
        for other in table.find_all('tr'):
            if other is row:break
            if other.find_parent('table') is table and not other.find('table'):
                h=canonical(str(other).encode())
                if frames(h):prior_rows.append(h)
        if prior_rows and len(frames(prior_rows[-1]))>=len(fs):header=prior_rows[-1];fs=frames(header)
        values,code=money_matches(rowtext[label.end():],external+' '+header)
        if code:reject(code,rowtext);continue
        if len(values)!=len(fs):reject('AMBIGUOUS_TABLE_COLUMNS',rowtext,headers=[f['header'] for f in fs],value_count=len(values));continue
        row_start=text.find(rowtext,max(table_start,0))
        for f,v in zip(fs,values):
            emit(f,v,rowtext,row_start,{'headers':header,'surrounding_context':external,'table_prefix':tabletext[:local],'metric_label':label[0],'amount_column':fs.index(f)},'table')
    # Narrative clauses retain their own explicit fiscal frame. They never
    # inherit a period from a preceding quarterly paragraph.
    for node in soup.find_all(['p','li','div']):
        if node.find_parent('table') or node.find(['p','li','div','table']):continue
        paragraph=canonical(str(node).encode())
        if not re.search(r'guidance|outlook|expects|targets|expected|revenue',paragraph,re.I):continue
        clauses=re.split(r'(?<=\.)\s+(?=(?:For\b|The Company\b|We expect\b))',paragraph)
        for clause in clauses:
            labels=list(re.finditer(r'\b(?:(?:total|net|consolidated)\s+)?revenues?\b',clause,re.I))
            for label in labels:
                left=clause[:label.start()]
                clause_start=text.find(clause);support=text[max(0,clause_start-400):clause_start]
                if INELIGIBLE.search(left[-45:]):
                    if re.search(r'annual recurring|ARR',left[-45:],re.I):reject('NON_CONSOLIDATED_METRIC',clause)
                    continue
                if not re.search(r'expects|expected|guidance|targets|outlook',clause,re.I) and not re.search(r'(?:expects|targets|guidance|outlook)[^.!?]{0,160}$',support,re.I):continue
                if re.search(r'achieved|reported|delivered|financial highlights',left[-150:],re.I):continue
                fs=frames(clause)
                if not fs:
                    bare_periods=re.findall(r'\b(?:first|second|third|fourth)\s+quarter\b|\bfull\s+(?:fiscal\s+)?year\b',clause,re.I)
                    if len(bare_periods)>1:
                        reject('AMBIGUOUS_MULTI_TARGET_CLAUSE',clause);continue
                    # A short revenue row may follow an explicit targets header.
                    a=text.find(clause);prefix=text[max(0,a-350):a];fs=frames(prefix)[-1:]
                    if not re.search(r'targets|guidance|outlook|expects|expected',prefix,re.I):fs=[]
                values,code=money_matches(clause[label.end():],clause)
                if not values:continue
                if len(fs)!=1:reject('AMBIGUOUS_PROSE_FISCAL_CONTEXT',clause,headers=[f['header'] for f in fs]);continue
                if len(values)!=1:reject('AMBIGUOUS_PROSE_AMOUNTS',clause);continue
                # Quote keeps the complete target clause, not just matching dollars.
                a=text.find(clause);emit(fs[0],values[0],clause,a,{'fiscal_context':fs[0]['header'],'supporting_context':support,'metric_label':label[0]},'prose')
    unique={}
    for c in observations:
        key=(c['metric'],c['start'],c['end'],Decimal(c['low']),Decimal(c['high']))
        if key not in unique or c['origin']=='table':unique[key]=c
    return text,list(unique.values()),abstentions


def assign_status(c,prior,metadata):
    """Compare only verified revenue observations of the identical target."""
    key=(c['company'],c['metric'],c['start'],c['end']);old=prior.get(key)
    if old and (old.get('company'),old.get('metric'),old.get('start'),old.get('end'))!=key:return None,'STATUS_REFERENCE_IDENTITY_MISMATCH'
    if old and not old.get('direct_guidance',False):return None,'NON_DIRECT_STATUS_REFERENCE'
    if old and (old['unit'],old['basis'])!=(c['unit'],c['basis']):return None,'INCOMPARABLE_STATUS_REFERENCE'
    if old and old['filed']>c['filed']:return None,'FUTURE_STATUS_REFERENCE'
    if old:
        before=(Decimal(old['low']),Decimal(old['high']));after=(Decimal(c['low']),Decimal(c['high']))
        c['status_input_id']=old['id'];c['status_evidence']={'prior':before,'current':after,'same_metric_and_period':True}
        if before==after:
            if re.search(r'am\.htm|revised|8-ka',c['source_url'],re.I):return old['status'],'AMENDMENT_UNCHANGED_RANGE'
            return 'reaffirmed','EXACT_TARGET_RANGE_UNCHANGED'
        if after[0]>=before[0] and after[1]>=before[1]:return 'raised','EXACT_TARGET_RANGE_RAISED'
        if after[0]<=before[0] and after[1]<=before[1]:return 'lowered','EXACT_TARGET_RANGE_LOWERED'
        return None,'MIXED_ENDPOINT_REVISION'
    if c['metric']=='quarterly_consolidated_revenue':return 'initial','FIRST_DIRECT_QUARTER_RANGE_OBSERVED_NOT_ORIGINAL_VERIFIED'
    y=re.search(r'FY(\d{4})',c['fiscal_label'])[1]
    initial=re.search(r'initiates?\s+(?:its\s+)?full[ -]year\s+(?:FY|fiscal\s+(?:year\s+)?)\s*(?:'+y+'|'+y[-2:]+r')\s+(?:revenue\s+)?(?:guidance|targets)',metadata.get('document_text',''),re.I)
    if initial:
        c['status_evidence']={'explicit_quote':initial[0],'source_url':c['source_url']}
        return 'initial','EXPLICIT_INITIAL_ANNUAL_GUIDANCE'
    return None,'ANNUAL_STATUS_HISTORY_MISSING'


def references(body,metadata,prior):
    text=canonical(body);soup=BeautifulSoup(body,'html.parser');day=issuance(text,metadata);observed=[];blocked=[]
    for node in soup.find_all(['p','li','div']):
        if node.find('table') or node.find(['p','li','div']):continue
        paragraph=canonical(str(node).encode())
        match=re.search(r'reaffirm\w*|no anticipated change|toward(?:s)?\s+(?:the\s+)?high end|withdraw\w*|reinstat\w*',paragraph,re.I)
        if not match:continue
        if not re.search(r'revenue|guidance|targets|outlook',paragraph,re.I):continue
        if re.search(r'commitment|profitability|operating margin',paragraph,re.I) and not re.search(r'revenue|financial guidance|financial targets',paragraph,re.I):continue
        # Stop at a sentence boundary after the reference, and remove dates/
        # quarter labels that merely identify a prior release being referenced.
        end=len(paragraph);stop=re.search(r'\.[”"\']?\s',paragraph[match.end():])
        if stop:end=match.end()+stop.start()+1
        quote=paragraph[:end]
        target_clause=quote if re.search(r'toward',match[0],re.I) else quote[match.start():]
        clause=re.split(r'previously provided|as provided|provided in|provided on|that was|as disclosed|press release issued',target_clause,flags=re.I)[0]
        fs=frames(clause);years={f['year'] for f in fs}
        if not years:
            dm=re.search(r'fiscal year ending\s+('+DATE.pattern+r')',clause,re.I)
            if dm:
                d=DATE.search(dm[0]);years={int(d[3])-CALENDARS['companies'][metadata['company']]['end_year_offset']}
                fs.append({'year':next(iter(years)),'quarter':None,'direct':True,'header':dm[0]})
        short=re.findall(r'\bQ([1-4])\b|\b(first|second|third|fourth)\s+quarter',clause,re.I)
        wordmap={'first':1,'second':2,'third':3,'fourth':4}
        qs={int(n) if n else wordmap[w.lower()] for n,w in short}
        if len(years)==1:
            for q in qs:
                if not any(f['quarter']==q for f in fs):fs.append({'year':next(iter(years)),'quarter':q,'direct':True,'header':clause})
        if not fs or len(years)>1:
            blocked.append({'code':'AMBIGUOUS_REFERENCE_PERIOD','quote':quote,'source_url':metadata['source_url']});continue
        for f in fs:
            start,finish=period(metadata['company'],f['year'],f['quarter']);metric='quarterly_consolidated_revenue' if f['quarter'] else 'consolidated_revenue';key=(metadata['company'],metric,start,finish);old=prior.get(key)
            if not old or old['filed']>metadata['filed']:
                blocked.append({'code':'MISSING_REFERENCE','quote':quote,'metric':metric,'start':start,'end':finish,'source_url':metadata['source_url']});continue
            if not day:
                blocked.append({'code':'UNRESOLVED_ISSUANCE_DATE','quote':quote,'source_url':metadata['source_url']});continue
            a=text.find(quote)
            if a<0:continue
            status='withdrawn' if re.search(r'withdraw',match[0],re.I) else 'reaffirmed'
            if re.search(r'reinstat',match[0],re.I):
                blocked.append({'code':'REINSTATEMENT_REQUIRES_EXPLICIT_RANGE','quote':quote,'source_url':metadata['source_url']});continue
            c={**old,**{k:metadata[k] for k in ['company','accession','exhibit','source_url','filed']},'issued':{k:day[k] for k in ['start','end','precision']},'issuance_evidence':day,
                'status':status,'status_reason':'EXPLICIT_REFERENCE_SAME_METRIC_PERIOD','quote':quote,'quote_start':a,'quote_end':a+len(quote),
                'context':{'reference_period':f['header'],'prior_supporting_quote':old['quote'],'prior_source_url':old['source_url']},
                'reference_input_id':old['id'],'source_sha256':metadata.get('raw_sha256'),'canonical_sha256':hashlib.sha256(text.encode()).hexdigest(),'origin':'explicit_reference'}
            if status=='withdrawn':c['low']=c['high']=None
            c.pop('id',None);c['id']=record_id('v2-explicit-reference',c);observed.append(c)
    return observed,blocked
