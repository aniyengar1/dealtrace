"""Complete pinned source text and lossless compact table structure."""
def compact_document(doc):
    """Proposed package, not active inference preprocessing. Drops no source text.

All canonical text, all table cell text, row order, and nondefault spans remain.
Duplicate table.text/context and per-cell default/tag keys are removed. Complete
original source is pinned by hash. No v2-hit selection or truncation.
"""
    tables=[]
    for t in doc['tables']:
        spans=[[i,j,c['rowspan'],c['colspan']]
               for i,row in enumerate(t['rows']) for j,c in enumerate(row)
               if str(c['rowspan'])!='1' or str(c['colspan'])!='1']
        headers=[[i,j] for i,row in enumerate(t['rows']) for j,c in enumerate(row) if c['tag']=='th']
        tables.append({'id':t['id'],'start':t['start'],'end':t['end'],
            'rows':[[c['text'] for c in row] for row in t['rows']],
            'nondefault_spans':spans,'header_cells':headers})
    return {**doc,'tables':tables}

