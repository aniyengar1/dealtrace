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
# "and Company"/"and Co." is NOT a strippable corporate-form suffix --
# it's integral to several real, well-known legal names ("Eli Lilly
# and Company") -- the negative lookbehind keeps "company"/"co" from
# matching when directly preceded by "and ".
_TRAILING_LEGAL_SUFFIX_RE = re.compile(
    r",?\s*\b(incorporated|inc|corporation|corp|(?<!and )(?<!and\s)company|"
    r"(?<!and )(?<!and\s)co|limited|ltd|"
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
    "XOMA", "HIG", "USA", "USAR", "SMTC", "WHP",
    # Round-4 spot-check: a short raw EDGAR name/ticker that ordinary
    # title-casing mangled ("CVS Health" -> "Cvs Health", "HNI" -> "Hni",
    # "AES" -> "Aes", "ITGR" -> "Itgr") -- verified real tickers, not a
    # guess, same bar as the entries above.
    "CVS", "HNI", "AES", "ITGR",
    # Additional real, well-known tickers/initialisms found in the same
    # round-4 sweep of all 802 public deals' display names (see
    # tests/test_display_name.py for the methodology: dictionary
    # -filtered, individually verified, not an exhaustive ticker list).
    "TPG", "GIC", "IAA", "CBIZ", "NCR", "VICI", "AIP", "STG", "GCP",
    "BBBY", "AMD", "GSK", "SLB", "CRH", "IHS", "DNOW", "GTCR", "QEP",
    "RPT", "QTS", "LXP", "CNH", "MRC", "PGT", "PDC", "ODP", "PANW",
    "JMP", "BGSF", "WDC", "IPG", "SWN", "BMS", "UTI", "HMS",
    # Surfaced by the round-4 merger-vehicle-name fix (src.deal_metrics
    # ._best_named_sponsor): Atlas Air's real buyer consortium includes
    # J.F. Lehman & Company, named in its own filing text as "JFLCO".
    "JFLCO",
}

# Word-level stylization overrides -- same entity, just a capitalization
# no algorithm can recover from an all-caps source ("VMWARE" has no way
# to know the internal capital in "VMware"). Applied per word, so it
# still fires if the name appears as part of a longer phrase, not just
# as the entire cleaned name (unlike DISPLAY_NAME_OVERRIDES below).
WORD_OVERRIDES = {
    "VMWARE": "VMware",
    "MARINEMAX": "MarineMax",
    "AVALONBAY": "AvalonBay",
}

# Whole-name overrides for when the fix isn't a capitalization of the
# SAME word but an expansion to the fuller name a short acronym stands
# for ("DFH" -> "Dream Finders Homes") -- preferring the full name over
# preserving the acronym, the opposite of what ACRONYM_WHITELIST does.
# Keyed by the suffix-stripped name, uppercased.
DISPLAY_NAME_OVERRIDES = {
    "DFH": "Dream Finders Homes",
    # "LHC GROUP, INC." strips both "Inc." and "Group" as generic legal
    # suffixes (the iterative suffix-stripping loop removes them one
    # pass at a time), leaving bare "LHC" -- but "Group" here is part of
    # the real, publicly traded name ("LHC Group"), not a redundant
    # corporate-structure qualifier an EDGAR filer tacked on. Restoring
    # it as a whole-name override (rather than loosening the general
    # suffix regex, which strips "Group"/"Holdings"/etc. correctly for
    # many other real names) is the narrow fix.
    "LHC": "LHC Group",
}


def _strip_edgar_artifacts(name: str) -> str:
    n = name.strip()
    prev = None
    while prev != n:
        prev = n
        n = _EDGAR_STATE_TAG_RE.sub("", n).strip()
    return n


def _strip_legal_suffixes(name: str) -> str:
    """The trailing rstrip(",.") below cleans up a comma/period left
    dangling by the suffix removal ("Holdings, Inc." -> "Holdings,"
    after removing "Inc." -> "Holdings") -- but must only run when the
    regex actually matched something. Running it unconditionally on
    every pass would also strip a genuine trailing period from a name
    that was never a legal-suffix match at all ("H.I.G." -> "H.I.G",
    destroying real punctuation in an initialism)."""
    n = name.strip()
    prev = None
    while prev != n:
        prev = n
        stripped = _TRAILING_LEGAL_SUFFIX_RE.sub("", n).strip()
        candidate = stripped.rstrip(",.").strip() if stripped != n else stripped
        # A name that's ENTIRELY a suffix word ("Company" on its own,
        # a Target-side defined-term placeholder that leaked in from a
        # caller that didn't filter it) would otherwise strip to an
        # empty string -- keep the original instead of discarding all
        # information.
        n = candidate if candidate else n
        if not candidate:
            break
    return n


def _title_case_word(word: str) -> str:
    bare = re.sub(r"[^A-Za-z]", "", word)
    if not bare:
        return word
    if bare.upper() in WORD_OVERRIDES:
        return WORD_OVERRIDES[bare.upper()]
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
