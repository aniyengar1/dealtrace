"""Deterministic extraction (no LLM) of a deal's size: shares
outstanding as of the record date, and -- only when the filing states
one outright -- an aggregate transaction/equity value. Both are read
straight from the filing's own cached text (src.classify_deal_type.
_full_text), with the exact source sentence kept as a quote, the same
convention every other extracted fact in this pipeline follows.

Bulk deals only -- a curated deal has no cached full-text HTML to
parse at all (see src.deal_metrics._filing_definition_acquirer's
identical scope decision for acquirer resolution).

    from src.deal_size import extract_shares_outstanding, extract_aggregate_value
"""

import re
from typing import Optional

from src.classify_deal_type import _bulk_slug_to_cik_accession, _full_text
from src.entity_match import core_name

# Splits on a period that's a real sentence boundary, not a decimal
# point ("approximately 1.2% of the combined company" must stay one
# sentence) -- a lookaround on digits either side is enough, since SEC
# filing prose never abbreviates ("Mr.", "Inc.") mid-sentence in a way
# that would matter here: an abbreviation's period is never immediately
# followed by a digit, so it's never mistaken for a decimal point, and
# splitting ON it just yields a shorter sentence fragment instead of a
# wrong one.
_SENTENCE_SPLIT_RE = re.compile(r"(?<!\d)\.(?!\d)")

# A comma-formatted number of at least 1,000 -- share counts are
# effectively always written this way; requiring a comma cheaply rules
# out a stray small number (a vote tally, a page number) the same
# sentence might also contain.
_LARGE_NUMBER_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")


def _sentences_mentioning(text: str, *keywords: str) -> list[str]:
    """Sentence-like chunks (split on real sentence-ending periods,
    see _SENTENCE_SPLIT_RE) that mention every one of `keywords`,
    case-insensitively -- deliberately not one combined regex, since a
    single [^.]* run can't tell a decimal point from a sentence
    boundary either, the same problem _SENTENCE_SPLIT_RE exists to
    avoid."""
    return [
        chunk.strip()
        for chunk in _SENTENCE_SPLIT_RE.split(text)
        if all(re.search(re.escape(kw), chunk, re.IGNORECASE) for kw in keywords)
    ]


def extract_shares_outstanding(slug: str, target: str) -> Optional[dict]:
    """Returns {"value": int, "quote": str} or None. The record-date
    share count, read straight from the filing's own sentence -- never
    computed, inferred, or guessed."""
    if _bulk_slug_to_cik_accession(slug) is None:
        return None
    text = _full_text(slug)
    if not text:
        return None

    candidates = []
    # "there were" (the actual count-statement construction) is a
    # required third keyword -- "record date" + "outstanding" alone
    # also matches unrelated sentences that just happen to mention both
    # words (Healthpeak/Physicians Realty Trust: "Based upon the number
    # of outstanding shares on the record date... Healthpeak will issue
    # approximately 162,957,213 shares" is about NEW shares issued AS
    # MERGER CONSIDERATION, not either company's own current share
    # count -- it mentions both keywords, but never says "there were").
    for sentence in _sentences_mentioning(text, "record date", "outstanding", "there were"):
        m = _LARGE_NUMBER_RE.search(sentence)
        if not m:
            continue
        value = int(m.group(0).replace(",", ""))
        # A merger-of-equals filing states BOTH companies' own share
        # counts in separate sentences (Healthpeak/Physicians Realty
        # Trust) -- only the one naming this deal's own target is the
        # right count for ITS implied equity value.
        names_target = core_name(target) and core_name(target) in core_name(sentence)
        candidates.append((names_target, value, sentence.strip()))

    if not candidates:
        return None
    named = [c for c in candidates if c[0]]
    chosen = named[0] if named else candidates[0]
    return {"value": chosen[1], "quote": chosen[2]}


def _parse_dollar_amount(raw: str) -> Optional[float]:
    m = re.match(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million)?", raw.strip(), re.IGNORECASE)
    if not m:
        return None
    amount = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    if unit == "billion":
        return amount * 1_000_000_000
    if unit == "million":
        return amount * 1_000_000
    return amount


# Only phrases that unambiguously state THIS transaction's own total
# consideration -- deliberately NOT "aggregate purchase price of
# approximately $X" (tried first, but it isn't deal-specific enough:
# it matched a target's own PRIOR, unrelated seed-financing round in
# one filing's "Corvex Transactions" history section just as readily
# as an M&A deal value) or "total enterprise value" (a routine
# valuation-analysis multiple, and enterprise value includes debt,
# which this field must never be confused with -- see the deal page's
# own "implied equity value" label). A filing that only ever states an
# enterprise value, or no aggregate figure at all, correctly yields no
# match here rather than a mislabeled one.
_AGGREGATE_VALUE_RES = [
    re.compile(r"transaction\s+(?:is\s+)?valued at\s+approximately\s*(\$[\d,.]+\s*(?:billion|million)?)", re.IGNORECASE),
    re.compile(r"total\s+equity\s+value\s+of\s+approximately\s*(\$[\d,.]+\s*(?:billion|million)?)", re.IGNORECASE),
]


def extract_aggregate_value(slug: str) -> Optional[dict]:
    """Returns {"value": float, "quote": str} or None. Only a handful
    of filings state their own deal's aggregate value outright; most
    don't, and this correctly returns None for them rather than
    estimating one.

    A Background of the Merger narrative can state SEVERAL different
    equity values -- one per competing proposal during the negotiation
    (Party K's $13-18M vs. American Exchange Group's $19M letter of
    intent, both "total equity value of approximately", in the same
    filing) -- so a phrase matching more than one DISTINCT dollar
    figure is ambiguous about which one is the actual deal's own final
    value, and is skipped rather than guessed."""
    if _bulk_slug_to_cik_accession(slug) is None:
        return None
    text = _full_text(slug)
    if not text:
        return None
    for rx in _AGGREGATE_VALUE_RES:
        matches = list(rx.finditer(text))
        if not matches:
            continue
        values = {v for v in (_parse_dollar_amount(m.group(1)) for m in matches) if v is not None}
        if len(values) != 1:
            continue
        value = next(iter(values))
        m = matches[0]
        # The sentence containing the match, not just the matched
        # phrase itself -- a real, checkable quote, same convention as
        # extract_shares_outstanding.
        sentence = next((s for s in _sentences_mentioning(text, m.group(0)) if m.group(0) in s), m.group(0))
        return {"value": value, "quote": sentence.strip()}
    return None
