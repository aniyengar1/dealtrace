"""Interpretation proposals only. Source membership is not semantic validation."""
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

Role=Literal['metric','scope','period','units','basis','guidance_type','amount','issuance','status','surrounding_context','table_header']

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')
class Span(Strict):
    source_id:str
    start:int|None=None
    end:int|None=None
    quote:str
    roles:list[Role]=Field(default_factory=list,description='All roles this exact passage supports; no duplicate quotations needed. Role assignment remains subject to semantic review.')
    role:Role|None=None # Read original cached v2 proposals without changing them.

    @model_validator(mode='after')
    def require_roles(self):
        if not self.roles and self.role is None:raise ValueError('Evidence roles required')
        return self
class Money(Strict):
    value:str
    scale:Literal['1','1000','1000000','1000000000']
class Observation(Strict):
    source_id:str
    metric_label:str
    metric_class:Literal['consolidated_revenue','net_sales','arr','segment_revenue','other','ambiguous']
    scope:Literal['consolidated','segment','ambiguous']
    scope_support:Literal['explicit','inferred','unresolved']
    basis_kind:Literal['reported','constant_currency','organic','adjusted','ambiguous']
    scope_qualifiers:list[str]
    fiscal_year:int|None
    fiscal_quarter:int|None
    period_start:str|None
    period_end:str|None
    issued_start:str|None
    issued_end:str|None
    issued_precision:Literal['day','month','range','unknown']
    currency:Literal['USD','other','unknown']
    guidance_type:Literal['direct','implied','historical_reference','ambiguous']
    amount_style:Literal['range','point','absolute_tolerance','percentage_tolerance','none']
    low:Money|None
    high:Money|None
    center:Money|None
    tolerance:Money|None
    status:Literal['initial','reaffirmed','raised','lowered','withdrawn','reinstated','unresolved']
    status_support:Literal['first_observed_quarter','explicit_issuance','prior_range','unresolved']
    prior_observation_index:int|None
    table_id:str|None
    column_label:str|None
    table_row_index:int|None
    table_column_index:int|None
    evidence:list[Span]
    review_note:str
class Extraction(Strict):
    observations:list[Observation]
    unresolved_sections:list[str]
