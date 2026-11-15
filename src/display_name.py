"""Cleans a raw EDGAR/extracted company name into a website-ready
display form: strips legal suffixes ("Inc.", "Corp", "Holdings, Inc.")
and EDGAR state-of-incorporation artifacts ("\\DE\\", "/DE/"), then
title-cases words that are entirely uppercase in the source (an
all-caps EDGAR name has no case information to preserve) while leaving
already-mixed-case words untouched.

Distinguishing a genuine short acronym ("PTC", "ACV", "BP") from an
all-caps ordinary word ("END" in "LANDS' END") has no reliable
algorithmic answer without a dictionary -- EDGAR names are often
entirely uppercase, so there's no case signal to tell them apart
either. This resolves the ambiguity with: a small curated whitelist of
known acronyms (checked first, always preserved uppercase); any other
word of 2 letters or fewer is left alone too (more likely an
initialism than a real word at that length); words of 3+ letters not
in the whitelist get ordinary title-casing. This means a genuine but
uncommon abbreviation outside the whitelist will be title-cased
incorrectly -- a known, accepted "best effort" limitation, not a bug.

A tiny whole-name override table (DISPLAY_NAME_OVERRIDES) handles
stylizations no algorithm can recover from an all-caps source at all
("MARINEMAX" has no way to know the internal capital in "MarineMax").
"""

import re

_EDGAR_STATE_TAG_RE = re.compile(r"[\\/]\s*[A-Za-z]{1,3}\s*[\\/]\s*$")
_TRAILING_LEGAL_SUFFIX_RE = re.compile(
    r",?\s*\b(incorporated|inc|corporation|corp|company|co|limited|ltd|"
    r"l\.l\.c\.?|llc|l\.p\.?|lp|p\.l\.c\.?|plc|holdings?|holding|group|"
    r"international|technologies|systems?)\b\.?\s*$",
    re.IGNORECASE,
)

# Non-exhaustive, deliberately curated -- a company identifier short
# enough to be mistaken for an ordinary word, or that a generic
# title-casing pass would otherwise mangle. Includes the examples given
# directly, well-known global acronyms, and tickers/short names this
# pipeline has independently verified as real entities in earlier
# acquirer-name fixes this session.
ACRONYM_WHITELIST = {
    "BP", "PTC", "ACV", "GE", "HP", "EA", "IBM", "CBS", "NBC", "ABC",
    "KKR", "EQT", "GIP", "MSD", "DXC", "CSX", "CSR", "UHS", "WES",
    "FSK", "GBDC", "OBDC", "NI", "HGV", "SIC", "KCS", "RBA", "WBD",
    "MBI", "CHP", "CHMI", "GRI", "PIF", "GSP", "HEL", "LCIF", "SKNY",
    "XOMA",
}

# Whole-name overrides for stylizations that aren't recoverable from an
# all-caps source at all. Keyed by the suffix-stripped name, uppercased.
DISPLAY_NAME_OVERRIDES = {
    "MARINEMAX": "MarineMax",
}


def _strip_edgar_artifacts(name: str) -> str:
    n = name.strip()
    prev = None
    while prev != n:
        prev = n
        n = _EDGAR_STATE_TAG_RE.sub("", n).strip()
    return n


def _strip_legal_suffixes(name: str) -> str:
    n = name.strip()
    prev = None
    while prev != n:
        prev = n
        n = _TRAILING_LEGAL_SUFFIX_RE.sub("", n).strip()
        n = n.rstrip(",.").strip()
    return n


def _title_case_word(word: str) -> str:
    bare = re.sub(r"[^A-Za-z]", "", word)
    if not bare:
        return word
    if bare.upper() in ACRONYM_WHITELIST:
        return word.upper()
    if any(c.islower() for c in word):
        return word
    if len(bare) <= 2:
        return word
    return word.capitalize()


def clean_display_name(raw_name: str) -> str:
    n = _strip_edgar_artifacts(raw_name)
    n = _strip_legal_suffixes(n)
    n = _strip_edgar_artifacts(n)
    key = n.upper().strip()
    if key in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[key]
    words = [w for w in n.split(" ") if w]
    return " ".join(_title_case_word(w) for w in words).strip()
