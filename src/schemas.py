"""Pydantic schemas for structured extraction from merger proxy filings."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field

EventType = Literal[
    "first_contact",
    "nda",
    "proposal",
    "counteroffer",
    "board_meeting",
    "exclusivity",
    "diligence",
    "signing",
    "other",
]

DatePrecision = Literal["day", "month", "range", "unknown"]

ConsiderationType = Literal["cash", "stock", "mixed", "unknown"]

ProposalKind = Literal[
    "non_binding_indication",
    "formal_bid",
    "counteroffer",
    "suggested_valuation",
]

ValuationMethod = Literal["trading_comps", "precedent_transactions", "dcf", "other"]


SOURCE_QUOTES_DESCRIPTION = (
    "1 to 3 exact, verbatim, contiguous spans copied character-for-character "
    "from the source paragraphs -- never a paraphrase. Every number in this "
    "item's numeric fields must appear in at least one of these quotes."
)


class Event(BaseModel):
    date_text: str = Field(description="Date exactly as written in the filing")
    date_start: Optional[date] = Field(None, description="ISO start date, null if unknown")
    date_end: Optional[date] = Field(None, description="ISO end date, null if unknown")
    date_precision: DatePrecision
    event_type: EventType
    parties: list[str] = Field(description="Anonymized party labels, e.g. 'Party A'")
    summary: str
    source_paragraph_ids: list[str]
    source_quotes: list[str] = Field(
        min_length=1, max_length=3, description=SOURCE_QUOTES_DESCRIPTION
    )


class Proposal(BaseModel):
    date: str = Field(description="Date exactly as written in the filing")
    proposer: str
    recipient: str
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    currency: Optional[str] = None
    consideration_type: ConsiderationType
    proposal_kind: ProposalKind
    status: str
    source_paragraph_ids: list[str]
    source_quotes: list[str] = Field(
        min_length=1, max_length=3, description=SOURCE_QUOTES_DESCRIPTION
    )


class ValuationAnalysis(BaseModel):
    advisor: str
    method: ValuationMethod
    metric: str = Field(description="e.g. 'EV/Revenue', 'Equity Value/CY2024E LFCF'")
    multiple_low: Optional[float] = None
    multiple_high: Optional[float] = None
    implied_price_low: Optional[float] = None
    implied_price_high: Optional[float] = None
    key_assumptions: list[str] = Field(
        default_factory=list, description="e.g. WACC range, terminal growth rate"
    )
    source_paragraph_ids: list[str]
    source_quotes: list[str] = Field(
        min_length=1, max_length=3, description=SOURCE_QUOTES_DESCRIPTION
    )


SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "events": Event,
    "proposals": Proposal,
    "valuation_analyses": ValuationAnalysis,
}


class BackgroundExtraction(BaseModel):
    """One call's worth of output for the Background of the Merger section."""

    events: list[Event] = Field(default_factory=list)
    proposals: list[Proposal] = Field(default_factory=list)


class ValuationExtraction(BaseModel):
    """One call's worth of output for a financial advisor's opinion section."""

    valuation_analyses: list[ValuationAnalysis] = Field(default_factory=list)
