"""Exact location proposals only; never semantic approval or source rewriting."""
def roles(span):
    return set(span.roles)|({span.role} if span.role is not None else set())

def locate(span,document):
    original={'start':span.start,'end':span.end,'quote':span.quote,'source_id':span.source_id}
    matches=[]
    if document and span.quote:
        text=document['canonical_text'];start=0
        while (found:=text.find(span.quote,start))>=0:
            matches.append({'start':found,'end':found+len(span.quote)})
            start=found+1
    status='UNIQUE_EXACT_MATCH' if len(matches)==1 else 'REPEATED_EXACT_MATCH' if matches else 'MISSING_EXACT_MATCH'
    return {'original':original,'status':status,'matches':matches,
            'resolved':matches[0] if len(matches)==1 else None,
            'roles':sorted(roles(span)),
            'original_offsets_match':bool(document and span.start is not None and span.end is not None and
                0<=span.start<span.end and document['canonical_text'][span.start:span.end]==span.quote),
            'semantic_validation':'NOT_GUARANTEED'}
