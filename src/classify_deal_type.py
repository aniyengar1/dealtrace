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
from src.entity_match import _is_ticker_of, is_acronym_of, is_same_entity

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

# "X will become/becoming/surviving...as a wholly owned subsidiary of
# Y" is standard merger-recital phrasing across its several common verb
# forms ("will become" for a future-tense recital, "becoming" for a
# participial clause mid-sentence -- Diamondback/Endeavor: "Endeavor
# surviving the First Merger and becoming a wholly owned subsidiary of
# Diamondback" -- or "surviving ... as a[n] [indirect] wholly owned
# subsidiary of Y" for a merger-sub structure -- OppFi/BNCC: "Merger Sub
# surviving as a wholly owned subsidiary of OppFi"; USAR/SVRE: "Merger
# Sub surviving the merger as an indirect, wholly owned subsidiary of
# USAR"); which of X/Y fuzzy-matches the stored target vs acquirer
# tells us directly whether discovery's labels are backwards, instead
# of inferring it from negotiation behavior.
_SUBSIDIARY_OF_RE = re.compile(
    _NAME_RUN + r"\s+(?:will\s+become|becoming|became|surviv\w*(?:\s+the\s+\w+)?\s+as)\s+"
    r"(?:an?|the)\s+(?:indirect,?\s+)?wholly[- ]owned\s+subsidiary\s+of\s+" + _NAME_RUN
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


_SPONSOR_DEF_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+)\s+((?:[A-Z][\w&'\-]*\s+){1,4}?)"
    r"(?:Corp\.?|Corporation|Inc\.?|LLC|L\.L\.C\.?|L\.P\.?|LP)\b[,.]?\s*"
    r"(?:a\s+\w+\s+corporation\s*)?\(\s*[“\"]([A-Za-z0-9]{2,10})[”\"]\s*\)"
)


def _shared_sponsor_brand(text: str, target: str, acquirer: str) -> bool:
    """True when the filing's own party-definition sentences ("Brand X
    Corp...(\"X\")") independently tag BOTH the target and the acquirer
    with the SAME leading brand word -- "BlackRock Capital Investment
    Corp. (\"BCIC\")" and "BlackRock TCP Capital Corp. (\"TCPC\")" both
    start with "BlackRock," confirming the same external-management
    sponsor on both sides of the merger, the structural tell behind an
    affiliated-BDC-complex merger even when neither party's own name
    uses an "...Advisor(s)/Adviser(s)" suffix the signing-event-party
    check (_is_affiliated_manager_merger) would otherwise catch.

    Requires the target-tagging match and the acquirer-tagging match to
    be two DISTINCT definitions, not the same one satisfying both --
    target and acquirer are occasionally just the same real company
    under two different name forms (a holdco legal name vs. its own
    brand name, e.g. "BTRS Holdings Inc." / "Billtrust"), and a single
    "BTRS Holdings Inc. (\"Billtrust\")" definition trivially matches
    both sides of that identity without saying anything about a shared
    THIRD-PARTY sponsor at all."""
    target_identity = acquirer_identity = None
    for m in _SPONSOR_DEF_RE.finditer(text):
        brand, rest, ticker = m.group(1), m.group(2).strip(), m.group(3)
        full = f"{brand} {rest}".strip()
        identity = (brand.lower(), ticker.lower(), full.lower())
        if target_identity is None and (is_same_entity(ticker, target) or is_acronym_of(ticker, target) or is_same_entity(full, target)):
            target_identity = identity
        if acquirer_identity is None and (is_same_entity(ticker, acquirer) or is_acronym_of(ticker, acquirer) or is_same_entity(full, acquirer)):
            acquirer_identity = identity
    if not target_identity or not acquirer_identity or target_identity == acquirer_identity:
        return False
    return target_identity[0] == acquirer_identity[0]


def _is_affiliated_manager_merger(slug: str, events: list[dict], target: str, acquirer: str) -> bool:
    parties = _signing_event_parties(events)
    for p in parties:
        if is_same_entity(p, target) or is_same_entity(p, acquirer):
            continue
        if not _ADVISER_SUFFIX_RE.search(p):
            continue
        others = [x for x in parties if x != p] + [target, acquirer]
        if _shares_root_with_another_party(p, others):
            return True
    return _shared_sponsor_brand(_full_text(slug), target, acquirer)


def _is_same_entity_fuzzy(a: str, b: str) -> bool:
    return (
        is_same_entity(a, b)
        or is_acronym_of(a, b)
        or is_acronym_of(b, a)
        or _is_ticker_of(a, b)
        or _is_ticker_of(b, a)
    )


def _is_filer_reversed(slug: str, target: str, acquirer: str) -> bool:
    """True when the filing's own text proves the stored `target` (the
    filer, under discovery's filer-is-target assumption) is actually
    the one doing the acquiring -- either in its own first-person voice
    ("our acquisition of X", "we will acquire X", checked against
    `acquirer`), or because some OTHER party is reported becoming a
    wholly owned subsidiary of `target` itself (Bunge/Viterra: "Viterra
    will become a wholly owned subsidiary of Bunge" -- Bunge is the
    stored target, and it cannot simultaneously be the one bought out;
    the OTHER name in that sentence doesn't need to match the stored
    acquirer field at all, since the real target is sometimes a THIRD
    party -- e.g. Viterra, USAR/SVRE -- that discovery's acquirer field
    never captured in the first place). Deliberately airtight either
    way: a company cannot both become someone's subsidiary AND absorb
    someone else as its own subsidiary in the same transaction."""
    text = _full_text(slug)
    for m in _FIRST_PERSON_BUYER_RE.finditer(text):
        acquired_name = next((g for g in m.groups() if g), None)
        if acquired_name and _is_same_entity_fuzzy(acquired_name.strip(), acquirer):
            return True
    for m in _SUBSIDIARY_OF_RE.finditer(text):
        parent = m.group(2).strip()
        if _is_same_entity_fuzzy(parent, target):
            return True
    return False


# Deliberately narrow: a bare "internalization" or "Share Issuance
# Proposal" is each, independently, too common to use alone -- "Share
# Issuance Proposal" is the standard proxy heading for ANY stock
# -consideration M&A deal needing a shareholder vote (not specific to
# internalizations), and "internalization" shows up in ordinary
# business-operations language with no connection to a management
# contract at all (Drilling Tools International's own risk factors
# discuss "internalization of repair and refurbishment activities" --
# an operational efficiency move, nothing to do with absorbing an
# external MANAGER). This only fires when "internaliz..." /
# "novation" / "no longer...externally managed" appears specifically
# tied to a MANAGEMENT AGREEMENT or MANAGER/ADVISER, the real
# structural tell behind Royalty Pharma: "RPM"/"RPI" are RPH's own
# external manager entities, novated out of existence in exchange for
# new RPH shares, not a buyout of RPH's public shareholders.
_MANAGER_INTERNALIZATION_RE = re.compile(
    r"internaliz\w*\s+(?:of\s+)?(?:the\s+|its\s+|our\s+)?(?:external\s+)?manage(?:ment|r)\b|"
    r"no longer\s+(?:be\s+)?an?\s+externally managed\b|"
    r"manage(?:ment|r)\s+agreements?\b.{0,100}\bnovat\w*\b|"
    r"\bnovat\w*\b.{0,100}\bmanage(?:ment|r)\s+agreements?\b",
    re.IGNORECASE,
)


_PURCHASE_AGREEMENT_RE = re.compile(r"\bPurchase Agreement\b")
_MERGER_AGREEMENT_RE = re.compile(r"\bMerger Agreement\b")


def _is_manager_internalization(text: str) -> bool:
    """Even tied to management-agreement language, "internalization"
    still shows up constantly in ordinary, unrelated third-party
    acquisitions of an externally managed REIT/BDC -- as financial
    -statement commentary on a PAST internalization ("EBITDA, adjusted
    for the internalization of management"), a dated defined term
    ("'Internalization' means...effective January 1, 2019"), or a
    hypothetical post-closing OPTION the ACQUIRER may or may not
    exercise ("SAFE will have the option...to internalize STAR's
    management") -- none of which make the CURRENT deal itself an
    internalization (Watermark/Brookfield, New Senior/Ventas, Bluerock/
    Blackstone, and Safehold/STAR were all real, ordinary third-party
    acquisitions that just happened to mention the word). The one
    reliable structural discriminator found empirically: a genuine
    internalization is structured as a "Purchase Agreement" (RPH
    purchasing out its own manager's contract) with NO "Merger
    Agreement" anywhere in the filing at all -- every ordinary
    acquisition, by contrast, has a Merger Agreement as its operative
    document, whether or not it also mentions internalization
    somewhere."""
    return bool(
        _MANAGER_INTERNALIZATION_RE.search(text)
        and _PURCHASE_AGREEMENT_RE.search(text)
        and not _MERGER_AGREEMENT_RE.search(text)
    )


def classify_deal(
    slug: str, target: str, acquirer: str, events: list[dict]
) -> tuple[str, bool, Optional[str]]:
    """Returns (deal_type, excluded_from_stats, exclusion_reason). A
    deal is included in stats/listings only when none of the exclusion
    signals below fires -- in effect a positive-inclusion rule, since
    every one of these signals is itself grounded in the filing's own
    affirmative description of what happens to the FILER's shares (do
    they get bought out, or does the filer end up absorbing someone
    else / issuing new shares to its own manager): spin-off/
    distribution (strongest, least ambiguous -- a literal filing-text
    phrase), affiliated-manager merger (two entities under the same
    external manager/sponsor), manager internalization (the filer
    issues new shares to absorb and terminate its own external
    manager's contract), then filer-reversal (the filer is reported
    acquiring/absorbing someone else, not being bought out itself).
    reverse_merger is flagged but never excludes -- it's still a real
    sale process, just one where the legal "acquirer" ends up
    controlled by the legal "target"'s former owners."""
    if _is_spin_off(slug):
        return (
            "spin_off",
            True,
            "spin-off / parent distribution of a subsidiary stake to its own shareholders, not an arm's-length sale process",
        )
    if _is_affiliated_manager_merger(slug, events, target, acquirer):
        return (
            "affiliated_manager_merger",
            True,
            "merger between entities under the same external manager/adviser, not an open competitive sale process",
        )
    if _is_manager_internalization(_full_text(slug)):
        return (
            "manager_internalization",
            True,
            "the filer is internalizing (absorbing) its own external manager via a share issuance, not being acquired by or acquiring anyone",
        )
    if _is_filer_reversed(slug, target, acquirer):
        return (
            "filer_is_acquirer",
            True,
            "the filer (recorded here as target) is actually the acquirer, or is absorbing a third party -- target/acquirer are reversed or mislabeled for this deal",
        )
    if _is_reverse_merger_text(slug):
        return "reverse_merger", False, None
    return "acquisition", False, None
