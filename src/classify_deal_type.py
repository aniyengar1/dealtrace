"""Classifies each deal's transaction structure using rules only (no
LLM) against already-extracted events/proposals and the cached filing
HTML, to catch four patterns a 20-deal spot-check surfaced that a plain
"M&A sale process" stat shouldn't include, or should at least label:

    from src.classify_deal_type import classify_deal

- spin_off: a parent distributing a subsidiary stake to its own
  shareholders (BellRing <- Post), not an arm's-length sale -- excluded.
- affiliated_manager_merger: a merger between two entities under the
  same external manager/adviser (Golub Capital BDC 3 <- GBDC) -- these
  don't have a normal competitive bidding process, so counting their
  "bidders"/"parties contacted" alongside real sale processes would be
  misleading -- excluded.
- filer_is_acquirer: the filing's own text describes the filer
  (always recorded as "target" by this pipeline's discovery step,
  which assumes whoever filed the document is the one being acquired)
  as the one doing the acquiring instead -- either in its own
  first-person voice ("our acquisition of X", "we will acquire X") or
  via a "X will become a wholly owned subsidiary of Y" recital where X
  fuzzy-matches the stored acquirer and Y fuzzy-matches the stored
  target (Viasat/Inmarsat: Viasat filed, and bought, Inmarsat; Adobe/
  Figma: Adobe's S-4 names Figma becoming Adobe's subsidiary, while
  this pipeline's discovery recorded Adobe as "target" since Adobe was
  the filer) -- excluded, since target_display/acquirer_display are
  backwards for these and nothing here attempts to un-swap them.

  Deliberately NOT based on proposal direction (which proposer sent
  more of a deal's proposals) -- tried first, but an ordinary target
  -shops-itself negotiation has the TARGET submitting plenty of its own
  counter-proposals back at the acquirer (rejections, demands for a
  higher price), which outnumbered the acquirer's own proposals often
  enough to falsely flag several genuine, correctly-labeled deals
  (Chembio Diagnostics, Phillips 66, Chevron, Anworth Mortgage) as
  reversed. Checking the filing's own stated transaction structure
  instead avoids that: it doesn't matter how a negotiation unfolded,
  only what the signed agreement says will happen to whom.
- reverse_merger: the filing's own text describes the deal as a
  reverse merger (Movano <- Corvex) -- flagged (deal_type set) but kept
  in stats, since it's still a real sale process, just one where the
  legal "acquirer" ends up controlled by the legal "target"'s former
  owners.

Every check works off already-stored data: no new Gemini/Vertex calls.
_is_spin_off and _is_reverse_merger need the full cached filing HTML
(the signal is usually on the cover page, outside the extracted
background-of-the-merger section); bulk_run.load_cached_html never
re-fetches, only reads what's already on disk, and a curated deal
(whose slug doesn't encode a CIK/accession) is given neither check and
defaults to "acquisition" unless one of the other two rules catches it.
"""

import re
from functools import lru_cache
from typing import Optional

from bs4 import BeautifulSoup

from src.bulk_run import load_cached_html
from src.entity_match import is_acronym_of, is_same_entity

# Deliberately NOT bare "spin-off"/"spinoff"/"split-off"/"spinco" --
# those words show up constantly in ordinary anti-dilution boilerplate
# ("a stock dividend, stock split, reverse stock split, separation,
# spinoff, reorganization...") that has nothing to do with the deal's
# own structure, and matched 297 of 964 canonical deals on that alone.
# "Reverse Morris Trust" is the one bare phrase precise enough to use
# standalone -- a specific tax-structuring term that, empirically
# across this dataset, only ever appears when the deal actually is one
# (Waters/BD, Dana/Eaton, Neogen/3M's food-safety spin-merger).
_RMT_RE = re.compile(r"\breverse morris trust\b", re.IGNORECASE)
# A parent distributing "its interest"/"its stake"/"shares of [SpinCo]"
# in a subsidiary to its own shareholders -- the structural tell behind
# BellRing/Post even where the filing never uses the word "spin-off"
# itself.
_DISTRIBUTION_RE = re.compile(
    r"\bdistribut(?:e|ion)(?:\s+of)?\b[^.]{0,80}\b(?:interest|stake|shares?)\s+in\b"
    r"[^.]{0,80}\bto\s+(?:its\s+|the\s+)?(?:shareholders|stockholders)\b",
    re.IGNORECASE,
)
_REVERSE_MERGER_RE = re.compile(r"\breverse merger\b", re.IGNORECASE)

_ADVISER_SUFFIX_RE = re.compile(r"\b(advisors?|advisers?)\b", re.IGNORECASE)
_ADVISER_SUFFIX_STRIP_RE = re.compile(r"\b(advisors?|advisers?)\b.*$", re.IGNORECASE)

# A bounded run of capitalized words (no period/comma inside), so a
# match can't cross a sentence boundary into unrelated text, and can't
# match an ordinary lowercase common-noun object either ("our
# acquisition of additional mineral and royalty interests" -- routine
# business boilerplate about buying oil-and-gas interests, unrelated to
# the M&A deal itself, appears in several filings' risk-factor
# sections and must NOT be mistaken for a merger-structure recital).
_NAME_RUN = r"([A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,4})"

# The filer explicitly describing ITSELF, in its own first-person
# voice, as the one buying the other side -- Viasat's registration
# statement (filed by Viasat for its own stock issuance) says "our
# acquisition of all of the issued and outstanding ordinary shares of
# [Inmarsat]." A merger proxy/S-4's ordinary third-person recitals
# ("Figma... entered into an Agreement and Plan of Merger... with
# Adobe") never use "our"/"we" this way, so this only fires for the
# rarer "acquirer solicits its own shareholders" filing structure.
# Requires the acquired party's name to immediately follow (the
# _NAME_RUN capture group) -- without it, "our acquisition of" also
# matches routine asset-purchase boilerplate completely unrelated to
# this deal's own structure (see _NAME_RUN's comment); the capture is
# then checked against the stored target in _is_filer_reversed, not
# accepted on its own.
_FIRST_PERSON_BUYER_RE = re.compile(
    r"\bour (?:acquisition|purchase) of\s+(?:all(?:\s+of)?\s+(?:the\s+)?(?:issued\s+and\s+outstanding\s+)?(?:shares|stock|ordinary\s+shares)\s+of\s+)?"
    + _NAME_RUN
    + r"|\bwe will (?:acquire|purchase)\s+" + _NAME_RUN
    + r"|\bwe have agreed to (?:acquire|purchase)\s+" + _NAME_RUN,
    re.IGNORECASE,
)

# "X will become a wholly owned subsidiary of Y" is standard
# merger-recital phrasing; which of X/Y fuzzy-matches the stored target
# vs acquirer tells us directly whether discovery's labels are
# backwards, instead of inferring it from negotiation behavior.
_SUBSIDIARY_OF_RE = re.compile(
    _NAME_RUN + r"\s+will\s+become\s+a\s+wholly[- ]owned\s+subsidiary\s+of\s+" + _NAME_RUN
)


def _bulk_slug_to_cik_accession(slug: str) -> Optional[tuple[str, str]]:
    if not slug.startswith("bulk_"):
        return None
    _, cik, accession_nodash = slug.split("_")
    accession = f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:18]}"
    return cik, accession


@lru_cache(maxsize=None)
def _full_text(slug: str) -> str:
    parsed = _bulk_slug_to_cik_accession(slug)
    if parsed is None:
        return ""
    html = load_cached_html(*parsed)
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(" ", strip=True)


def _is_spin_off(slug: str) -> bool:
    text = _full_text(slug)
    return bool(_RMT_RE.search(text) or _DISTRIBUTION_RE.search(text))


def _is_reverse_merger_text(slug: str) -> bool:
    return bool(_REVERSE_MERGER_RE.search(_full_text(slug)))


def _signing_event_parties(events: list[dict]) -> list[str]:
    for e in events:
        if e.get("event_type") == "signing":
            return [p for p in (e.get("parties") or []) if p]
    return []


def _shares_root_with_another_party(adviser_name: str, other_names: list[str]) -> bool:
    """True if `adviser_name` (an "...Advisor(s)/Adviser(s)" party) is
    plausibly named AFTER one of the deal's own companies -- "GC
    Advisors" for "Golub Capital", "BSPRT Advisor" for "BSPRT" -- rather
    than an independent, unrelated investor fund ("Perceptive Advisors,
    LLC" shares no name with either side of a biotech merger it was
    just providing financing for). A bare "Advisor"/"Adviser" with no
    distinguishing name of its own is treated as a match by default --
    a merger agreement naming one as its own co-signing party is itself
    already a strong, rare enough signal on its own."""
    root = _ADVISER_SUFFIX_STRIP_RE.sub("", adviser_name).strip(" ,.")
    if not root:
        return True
    root_lower = root.lower()
    for other in other_names:
        if not other:
            continue
        other_lower = other.strip().lower()
        if not other_lower:
            continue
        if other_lower.startswith(root_lower) or root_lower.startswith(other_lower):
            return True
        if is_acronym_of(root, other):
            return True
    return False


def _is_affiliated_manager_merger(events: list[dict], target: str, acquirer: str) -> bool:
    parties = _signing_event_parties(events)
    for p in parties:
        if is_same_entity(p, target) or is_same_entity(p, acquirer):
            continue
        if not _ADVISER_SUFFIX_RE.search(p):
            continue
        others = [x for x in parties if x != p] + [target, acquirer]
        if _shares_root_with_another_party(p, others):
            return True
    return False


def _is_same_entity_fuzzy(a: str, b: str) -> bool:
    return is_same_entity(a, b) or is_acronym_of(a, b) or is_acronym_of(b, a)


def _is_filer_reversed(slug: str, target: str, acquirer: str) -> bool:
    """True when the filing's own text describes the stored `acquirer`
    becoming a subsidiary of the stored `target`, or describes the
    filer (discovery's stored `target`, under the filer-is-target
    assumption) in its own first-person voice as the one buying the
    company stored as `acquirer` -- either way, proof that the
    assumption was wrong for this deal (see module docstring)."""
    text = _full_text(slug)
    for m in _FIRST_PERSON_BUYER_RE.finditer(text):
        acquired_name = next((g for g in m.groups() if g), None)
        if acquired_name and _is_same_entity_fuzzy(acquired_name.strip(), acquirer):
            return True
    for m in _SUBSIDIARY_OF_RE.finditer(text):
        subsidiary, parent = m.group(1).strip(), m.group(2).strip()
        if _is_same_entity_fuzzy(subsidiary, acquirer) and _is_same_entity_fuzzy(parent, target):
            return True
    return False


def classify_deal(
    slug: str, target: str, acquirer: str, events: list[dict]
) -> tuple[str, bool, Optional[str]]:
    """Returns (deal_type, excluded_from_stats, exclusion_reason).
    Checked in this order: a spin-off/distribution is the strongest,
    least ambiguous signal (a literal filing-text phrase), followed by
    the affiliated-manager structural signal, then the filer-reversal
    signal (filing-text-based, see _is_filer_reversed), then
    reverse-merger (flag only, never excludes)."""
    if _is_spin_off(slug):
        return (
            "spin_off",
            True,
            "spin-off / parent distribution of a subsidiary stake to its own shareholders, not an arm's-length sale process",
        )
    if _is_affiliated_manager_merger(events, target, acquirer):
        return (
            "affiliated_manager_merger",
            True,
            "merger between entities under the same external manager/adviser, not an open competitive sale process",
        )
    if _is_filer_reversed(slug, target, acquirer):
        return (
            "filer_is_acquirer",
            True,
            "the filer (recorded here as target) is actually the acquirer -- target/acquirer are reversed for this deal",
        )
    if _is_reverse_merger_text(slug):
        return "reverse_merger", False, None
    return "acquisition", False, None
