"""Shared fuzzy company-name matching, used by acquirer-guessing,
dedup, and headline stats alike.

The underlying problem: extracted proposer/recipient/parties text uses
informal short names ("Knoll", "Waters"), while deal_candidates.target_name
(and deals.target) is EDGAR's raw legal name ("KNOLL INC", "WATERS CORP
/DE/"). Exact-string-equality checks against the raw legal name (the
previous approach) miss this almost every time, which has two
consequences: a deal's own short name gets miscounted as a candidate
"acquirer" (because it doesn't exactly equal the legal name), and
signing/placeholder resolution silently fails the same way. core_name
strips the legal-entity noise (Inc/Corp/suffixes, parenthetical state
tags) so "Knoll" and "KNOLL INC" compare equal.
"""

import re

_PAREN_SUFFIX_RE = re.compile(r"[/\\][^/\\]*[/\\]")
_LEGAL_SUFFIX_RE = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|co|limited|ltd|"
    r"l\.l\.c|llc|l\.p|lp|plc|holdings?|group|international|"
    r"technologies|systems?)\b\.?",
    re.I,
)
_PUNCT_RE = re.compile(r"[^\w\s]")
_SPACE_RE = re.compile(r"\s+")


def core_name(name: str) -> str:
    """Lowercased, legal-suffix-stripped identity for a company name --
    "KNOLL INC" and "Knoll" both reduce to "knoll"."""
    n = name.strip().lower()
    n = _PAREN_SUFFIX_RE.sub(" ", n)
    n = _LEGAL_SUFFIX_RE.sub(" ", n)
    n = _PUNCT_RE.sub(" ", n)
    return _SPACE_RE.sub(" ", n).strip()


def is_same_entity(name_a: str, name_b: str) -> bool:
    """True if two company names plausibly refer to the same entity --
    exact core-name match, or one core name is a prefix of the other
    (catches "Herman Miller" vs "Herman Miller Inc" vs a filing's
    "Herman Miller Furniture" type variants) as long as the shared
    prefix isn't trivially short."""
    if not name_a or not name_b:
        return False
    a, b = core_name(name_a), core_name(name_b)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 3 and longer.startswith(shorter)
