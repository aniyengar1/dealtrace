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


def initials(name: str) -> str:
    """"United States Steel Corp" -> "USS" (legal suffix stripped first,
    so "Corp" doesn't contribute a letter)."""
    words = core_name(name).split()
    return "".join(w[0] for w in words if w).upper()


def _initials_including_suffix(name: str) -> str:
    """Some real tickers DO include a letter from the legal suffix --
    "Mechanical Technology Inc" -> "MTI", "Healthy Choice Wellness
    Corp." -> "HCWC" -- the opposite case from `initials`, which
    deliberately strips the suffix. "&" is treated as "and" so it still
    contributes a letter instead of vanishing as punctuation."""
    n = name.strip().lower().replace("&", " and ")
    n = _PAREN_SUFFIX_RE.sub(" ", n)
    n = _PUNCT_RE.sub(" ", n)
    words = _SPACE_RE.sub(" ", n).strip().split()
    return "".join(w[0] for w in words if w).upper()


_ANONYMIZED_PLACEHOLDER_RE = re.compile(
    r"^(the\s+)?(company|party|bidder|buyer|acquiror|acquirer|counterparty|sponsor)\s*[a-z0-9]{1,3}$",
    re.IGNORECASE,
)


def is_anonymized_placeholder(name: str) -> bool:
    """True for a filing's own anonymization label ("Company A", "Party
    B", "Bidder 1") -- never a real company, so never a valid answer for
    "who is the acquirer" even when it's the most frequently mentioned
    name in a deal's proposals (see Global Blood Therapeutics / Pfizer,
    where "Company A" outnumbered "Pfizer" by raw mention count)."""
    if not name:
        return False
    return bool(_ANONYMIZED_PLACEHOLDER_RE.match(name.strip()))


def is_acronym_of(short: str, long_name: str) -> bool:
    """True if `short` looks like an initials/acronym abbreviation of
    `long_name` -- "USS" for "UNITED STATES STEEL CORP". Requires the
    long name to have at least 2 significant words (so a single-word
    name can't trivially "match" any one-letter string) and the
    candidate acronym to look like one (letters only, 2-6 characters) --
    guards against an unrelated short name coincidentally matching."""
    s = short.strip()
    if not s or not s.isalpha() or not (2 <= len(s) <= 6):
        return False
    words = core_name(long_name).split()
    if len(words) < 2:
        return False
    return s.upper() in (initials(long_name), _initials_including_suffix(long_name))
