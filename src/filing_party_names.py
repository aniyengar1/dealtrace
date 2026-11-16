"""Parses the merger agreement's own party definitions directly out of
the cached filing text -- "by and among [Target], [Acquirer] ("Parent")
and [Merger Sub]" in a merger proxy, or "[Acquirer] ("Purchaser")" in a
tender offer -- as a more authoritative source for the acquirer's name
than frequency-counting proposer/recipient mentions
(src.bulk_quality_check.guess_acquirer).

    from src.filing_party_names import extract_acquirer_from_filing

Only scans the first ~400KB of the document: these definitions are
always in the cover page, summary, or opening recitals, never deep in
the background narrative, and scanning the full multi-megabyte
document (some are 8MB+) for every deal would be needlessly slow.
"""

import html as html_module
import re

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
SCAN_WINDOW_CHARS = 400_000

_QUOTE_CLASS = "\"“”"
_PARTY_DEF_RE = re.compile(
    r"\(\s*(?:the\s+)?[" + _QUOTE_CLASS + r"]\s*(Parent|Purchaser)\s*[" + _QUOTE_CLASS + r"]\s*\)",
    re.IGNORECASE,
)
_DESCRIPTIVE_CLAUSE_START_RE = re.compile(r",\s*(?:a|an)\s+", re.IGNORECASE)
# Comma is a connector EXCEPT right before a legal suffix ("Bausch
# Health Americas, Inc." must not split into "Bausch Health Americas"
# / "Inc." -- the comma there is part of one single name, not a list
# separator).
_LEGAL_SUFFIX_WORDS = (
    r"inc\.?|incorporated|corp\.?|corporation|llc|l\.l\.c\.?|lp|l\.p\.?|"
    r"ltd\.?|limited|plc|co\.?|company|sa|ag|nv|se|gmbh"
)
_CONNECTOR_SPLIT_RE = re.compile(
    r"\bby and among\b|\bamong\b|\bbetween\b|\bwith\b|\bby\b|"
    r"\band(?!\s+(?:" + _LEGAL_SUFFIX_WORDS + r")\b)\b|"
    r",(?!\s*(?:" + _LEGAL_SUFFIX_WORDS + r")\b)",
    re.IGNORECASE,
)
# "a wholly-owned (direct/indirect) subsidiary of X" / "an affiliate of
# X" / "a unit of X" / "a division of X" -- these relational phrases
# name the REAL party one level up from a shell ("Project Merci Merger
# Sub, Inc.... a wholly-owned indirect subsidiary of Biosynex SA");
# when present, the text after the LAST such phrase is the actual
# party name to use, overriding plain connector-splitting (which would
# otherwise stop at "and"/"," well before reaching the real name).
_RELATION_OF_RE = re.compile(
    r"\b(?:wholly[\s-]owned\s+)?(?:direct(?:ly)?\s+|indirect(?:ly)?\s+)?"
    r"(?:subsidiary|affiliate|unit|division)\s+of\s+",
    re.IGNORECASE,
)

_AFFILIATE_OF_RE = re.compile(
    r"(?:is|are)\s+(?:an?\s+)?affiliates?\s+of\s+(?:funds?\s+(?:advised|managed)\s+by\s+)?",
    re.IGNORECASE,
)
_DBA_RE = re.compile(r"(?:does|doing)\s+business\s+as\s+", re.IGNORECASE)
_SENTENCE_END_RE = re.compile(r"\s+and\s|\.\s|\.$|;|\(")

# Shell/holding-vehicle name patterns -- a named parent whose own name
# is just a deal-specific shell ("Heron BidCo, LLC", "Rand Parent,
# LLC", "Formulations Parent Corporation", "Cyclades Parent, Inc") is
# technically the defined party but not an informative answer to "who
# is the acquirer" the way a real operating company or PE firm name
# is. "Parent"/"Buyer" as a standalone word (not requiring an LLC/Inc
# suffix right after it -- "Formulations Parent" has none) is itself
# already a strong shell signal; real public companies essentially
# never have "Parent" or "Buyer" as part of their own name. Used both
# to decide whether to keep searching for an "affiliate of"/"does
# business as" refinement nearby, and by callers deciding whether to
# prefer an already-good heuristic answer over a shell -- never to
# discard the shell name outright, since it's still better than
# nothing when no refinement and no better heuristic answer exist.
_SHELL_NAME_RE = re.compile(
    r"\b(bidco|holdco|newco|mergeco|parentco|finco|topco|midco|"
    r"acquireco|acquisitionco|merger\s*sub|parent|buyer|purchaser|"
    r"guarantor|acquisition)\b",
    re.IGNORECASE,
)


def _clean_text(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html[:SCAN_WINDOW_CHARS])
    text = html_module.unescape(text)
    return _WS_RE.sub(" ", text)


def _strip_trailing_descriptive_clause(window: str) -> str:
    """Strips a trailing ", a Delaware corporation" / ", a company
    incorporated under the laws of..." clause -- uses the LAST such
    clause before the end of the window, not the first, since the
    window can contain other parties' own ", a ..." clauses earlier
    in the same "by and among A, a ..., B, a ..." sentence."""
    matches = list(_DESCRIPTIVE_CLAUSE_START_RE.finditer(window))
    if matches:
        window = window[: matches[-1].start()]
    return window.strip()


def _take_last_segment(window: str) -> str:
    """The window typically ends with a connector phrase ("by and
    among ... NAME") -- splits on connectors (by/among/between/with/
    and/,) and keeps the last segment, which is the actual party name
    immediately before the defined term's parenthetical (or before
    whatever relational phrase _candidate_for_match already cut at)."""
    parts = _CONNECTOR_SPLIT_RE.split(window)
    return parts[-1].strip() if parts else window.strip()


def _is_plausible_name(name: str, target: str) -> bool:
    if not name or len(name) < 2 or len(name) > 100:
        return False
    # A real company name can start with a digit ("1776 Portfolio
    # Investment, LLC", "3M") -- rejecting those meant a correct match
    # got skipped in favor of a later, address-block-garbled one
    # ("Colorado 80206 (720) 284-6400 1776 Portfolio Investment, LLC")
    # that only happened to pass because "Colorado" starts with a
    # capital letter.
    if not (name[0].isupper() or name[0].isdigit()):
        return False
    if re.search(r"\(\d{3}\)|\d{3}-\d{4}", name):
        return False
    # A ZIP code or suite number ("TX 75254", "NY 14209") reads as a
    # 3+ digit run NOT at the very start of the name -- unlike a
    # genuine leading-digit name ("1776 Portfolio Investment, LLC"),
    # which only has digits in that one leading position.
    if re.search(r"\d{3,}", re.sub(r"^\d+\s*", "", name)):
        return False
    from src.entity_match import is_acronym_of, is_same_entity

    if is_same_entity(name, target) or is_acronym_of(name, target):
        return False
    return True


def _extract_refinement(text: str, pattern: re.Pattern, search_start: int, search_end: int) -> str | None:
    """Looks for an "affiliate of X" / "does business as X" refinement
    within [search_start, search_end) of text, returning the cleaned
    name X, or None if the pattern isn't found there."""
    window = text[search_start:search_end]
    match = pattern.search(window)
    if not match:
        return None
    after = window[match.end():]
    end_match = _SENTENCE_END_RE.search(after)
    candidate = after[: end_match.start()] if end_match else after[:150]
    return _strip_trailing_descriptive_clause(candidate)


def _candidate_for_match(text: str, match: re.Match) -> str | None:
    """A "subsidiary of"/"affiliate of" relational phrase (see
    _RELATION_OF_RE) takes priority when present: it's checked on the
    RAW window first, before any descriptive-clause stripping, because
    the real party name it points to is often AFTER an earlier ", a
    Delaware corporation" clause that would otherwise get stripped
    away along with everything following it (Huttig/Woodgrain: "...by
    HBP Merger Sub, Inc., a Delaware corporation ("Merger Sub") and a
    wholly-owned subsidiary of Woodgrain Inc." -- stripping from the
    first ", a" trailing clause would destroy "subsidiary of Woodgrain
    Inc." entirely, well past where that clause starts)."""
    window_start = max(0, match.start() - 300)
    window = text[window_start : match.start()]

    # Only trust a relation phrase that's CLOSE to this definition (its
    # own clause), not one found anywhere in the 300-char lookback --
    # Archaea's window contains an earlier, unrelated "a subsidiary of
    # the Company" (describing a different party, "LFG Acquisition
    # Holdings LLC") well before BP's own clause; using it would cut
    # away BP's name entirely. Empirically, a genuine same-clause
    # relation phrase ends within ~70 chars of the window's end; the
    # false Archaea match ends 132 chars back.
    relation_matches = list(_RELATION_OF_RE.finditer(window))
    if relation_matches and len(window) - relation_matches[-1].end() <= 70:
        window = window[relation_matches[-1].end() :]
    window = _strip_trailing_descriptive_clause(window)

    name = _take_last_segment(window)
    return name.strip(" ,.;") or None


_OPAQUE_ACRONYM_RE = re.compile(r"^[A-Z]{2,6}$")


def is_shell_name(name: str) -> bool:
    """True for a named-but-uninformative party: a conventional shell/
    holdco pattern (_SHELL_NAME_RE), or a single opaque all-caps token
    with no spaces once the legal suffix is stripped ("LEWHP, LLC" ->
    "LEWHP") -- real companies are occasionally named this way too, but
    it's indistinguishable from a deal-specific project-code acronym,
    and in a real case (Lands' End/WHP Global) the filing's own
    "Purchaser" was exactly this kind of opaque shell while the
    heuristic's existing answer ("WHP Global", pulled from the filing's
    own later "(d/b/a WHP Global)" tag elsewhere) was already correct
    and more informative."""
    if _SHELL_NAME_RE.search(name):
        return True
    from src.display_name import _strip_legal_suffixes

    bare = re.sub(r"[^A-Za-z]", "", _strip_legal_suffixes(name))
    return bool(_OPAQUE_ACRONYM_RE.match(bare))


def extract_acquirer_from_filing(raw_html: str, target: str) -> str | None:
    """Best-effort extraction of the acquirer's name from the filing's
    own "Parent"/"Purchaser" party definition, preferring a nearby
    "affiliate of X" / "does business as X" refinement over a shell
    entity's own name (e.g. "Heron BidCo, LLC" -> look for its real
    parent) and preferring "Parent" over "Purchaser" when a filing
    defines both (a tender offer's Purchaser is often itself a shell
    subsidiary of the named Parent). Returns None if nothing usable is
    found, or if the only candidate is the target itself."""
    text = _clean_text(raw_html)

    matches_by_label: dict[str, list[re.Match]] = {"parent": [], "purchaser": []}
    for m in _PARTY_DEF_RE.finditer(text):
        matches_by_label[m.group(1).lower()].append(m)

    for label in ("parent", "purchaser"):
        for m in matches_by_label[label]:
            name = _candidate_for_match(text, m)
            if not name:
                continue

            refinement = _extract_refinement(text, _AFFILIATE_OF_RE, m.end(), m.end() + 400)
            if refinement is None:
                refinement = _extract_refinement(text, _DBA_RE, max(0, m.start() - 400), m.end() + 50)
            if refinement and _is_plausible_name(refinement, target):
                return refinement

            if is_shell_name(name):
                # A shell with no nearby refinement is still better
                # than nothing -- keep it as a fallback, but keep
                # looking at other matches/labels first in case one of
                # them has a cleaner name or a refinement.
                continue

            if _is_plausible_name(name, target):
                return name

    # Second pass: accept a shell name if that's all there is.
    for label in ("parent", "purchaser"):
        for m in matches_by_label[label]:
            name = _candidate_for_match(text, m)
            if name and _is_plausible_name(name, target):
                return name

    return None
