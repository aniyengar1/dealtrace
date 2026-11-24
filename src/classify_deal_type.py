"""Classifies each deal's transaction structure using rules only (no
LLM) against already-extracted events/proposals and the cached filing
HTML, to catch patterns a 20-deal spot-check surfaced that a plain
"M&A sale process" stat shouldn't include, or should at least label:

    from src.classify_deal_type import classify_deal

- spin_off: a parent distributing a subsidiary stake to its own
  shareholders (BellRing <- Post, IAC -> Vimeo), not an arm's-length
  sale -- excluded. Checked two ways: the specific "distribution of a
  stake in X to its shareholders" recital, or "a spin-off of X to Y's
  stockholders" naming the deal's own parties directly (IAC's board
  discussing "a spin-off of Vimeo to IAC's stockholders").
- self_reorganization: target and acquirer are each other's own
  pre-existing affiliate, not independent third parties -- a holding
  company interposed above an existing public company via merger
  (FTAI Finance Holdco Ltd., formed as an indirect subsidiary of FTAI
  before "acquiring" it in a holdco merger) or a parent reabsorbing its
  own already-majority-owned operating partnership (LXP Industrial
  Trust already owning ~99% of LCIF before "merging" with it) --
  excluded, same reasoning as spin_off (no competitive process is
  possible when there's no independent counterparty at all). The bare
  "reverse merger"/"reorganization" words alone don't trigger this --
  both stay included elsewhere (reverse_merger below; routine tax-
  qualification language is near-universal M&A boilerplate) -- only
  the deal's own text directly naming target/acquirer in the
  structural relationship does.
- affiliated_manager_merger: a merger between two entities under the
  same external manager/adviser (Golub Capital BDC 3 <- GBDC, FS KKR
  Capital Corp. II <- FSK) -- these don't have a normal competitive
  bidding process, so counting their "bidders"/"parties contacted"
  alongside real sale processes would be misleading -- excluded.
  Checked three ways: a signing-event party whose own name shares a
  root with the other side's name or the filing's own brand-defining
  sentences, or (when the shared manager is never actually named as a
  signing party at all, as for FSK/FSKR) the filing directly stating
  both sides "have the same adviser/manager."
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

  For an S-4 specifically, also fires whenever the ACQUIRER field's
  own named party -- not the target field's -- is the one whose
  shareholders are shown adopting the merger agreement: an S-4's filer
  is always the party registering new securities, but in a stock deal
  that's often a JOINT proxy statement/prospectus serving the real
  target's own shareholder vote too, so filer identity alone isn't
  enough (superseded _is_s4_filer_is_acquirer, which assumed it was).
- merger_of_equals: an S-4 that calls itself one, or where BOTH
  target's and acquirer's own shareholders are independently shown
  adopting the merger agreement (Hut 8/USBTC, Steel Newco/Pinnacle,
  Ballston Spa/NBC) -- kept in stats (not excluded), just labeled.
- buyer_side_s4_vote: an S-4 where NEITHER party has a found merger
  -adoption vote, and at least one votes on a share issuance only --
  i.e. only the real acquirer's own shareholders have any described
  vote at all (Bally's/Gamesys, Drilling Tools/DTI, AeroVironment) --
  excluded, since there's no real target-side sale process captured in
  this document.
- complex_structure: a hand-reviewed, slug-keyed set of deals whose
  structure is genuinely tangled -- a divestiture to a third-party
  buyer entity, a split-off combined with a merger, a holdco
  reorganization with no real second party (Eversource/Aquarion,
  Liberty Sirius XM/Liberty Media, Twin Vee) -- excluded with this
  distinct reason rather than spending further time untangling them.
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

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from src.bulk_run import load_cached_html
from src.entity_match import (
    _is_ticker_of,
    governance_body_subject,
    is_acronym_of,
    is_governance_body_reference,
    is_same_entity,
)

# BeautifulSoup-parsing a deal's full cached filing HTML (some are
# multi-megabyte) for every one of ~900 bulk deals is the dominant cost
# of a full deal_metrics recompute (~9 minutes, confirmed by timing a
# full run) -- cached to disk here, keyed by slug alone, since a cached
# filing's HTML never changes once fetched (SEC filings are immutable;
# this pipeline never re-fetches one, see bulk_run.load_cached_html).
# Not time/mtime invalidated for the same reason: there's nothing that
# would ever change the source HTML out from under an existing cache
# entry. Clearing a specific deal's cache (e.g. after a genuine re
# -fetch) means deleting its one file; a code change serious enough to
# need re-parsing EVERY deal has no reason to touch parsed text at all
# (only src.classify_deal_type's own regex logic would change, which
# the separate _CLASSIFY_CACHE below already re-runs on every call --
# only the raw text extraction is cached here).
_PARSED_TEXT_CACHE_DIR = Path("data/cache/parsed_filing_text")


def _parsed_text_cache_path(slug: str) -> Path:
    return _PARSED_TEXT_CACHE_DIR / f"{slug}.txt"


# Caches classify_deal()'s full result (deal_type, excluded_from_stats,
# exclusion_reason) -- even with _full_text() now cached, every call
# still re-runs several regex scans and _is_affiliated_manager_merger's
# signing-event-party comparisons, on every one of ~900 deals, on every
# recompute. Keyed on target/acquirer/the signing event's own type+
# parties (the only event fields any check here reads, per
# _signing_event_parties) plus _CLASSIFY_CACHE_VERSION, so a genuine
# change to those inputs -- or a deliberate version bump after a future
# rule change -- invalidates the right entries instead of silently
# serving a stale classification forever.
_CLASSIFY_CACHE_DIR = Path("data/cache/deal_type_classification")
# v2: added self_reorganization, the shared-manager-statement check in
# _is_affiliated_manager_merger, and the "spin-off of X to Y's
# stockholders" check in _is_spin_off. v3: tightened
# _is_self_reorganization's reverse-merger-of-into check to require
# BOTH captured names to match target/acquirer, not just one -- the
# looser version misclassified an ordinary reverse-merger-structured
# THIRD-PARTY sale (Cherry Hill/TPG Mortgage's "Party A", a real
# competing bidder, not an affiliate) as a self-reorganization. v4:
# added _is_proposal_direction_reversed (reads proposals, not just
# events -- a new cache-key input, see below), _is_new_holdco_merger,
# and _acquirer_is_target_governance_body, after the read-only bidder
# -count anomaly investigation found several role-reversal/self
# -reference shapes none of the v3 checks caught (Aon/NFP, Enova/
# Grasshopper, Maiden/Kestrel, Centennial/Colgate, Apollo/Athene,
# Strategic Storage Trust VI/SSGT III). v5: _is_proposal_direction_
# reversed now also weighs the deal's own FINAL "X will become a
# wholly owned subsidiary of Y" structure (not just proposal-text
# "acquire" language) and ignores a negated/contrastive "rather than an
# acquisition of X" frame -- without this, Desktop Metal/Stratasys and
# ReShape/Obalon were both wrongly flagged off an early, later
# -superseded proposal that pointed the opposite way from the deal's
# own final agreed structure. v6: added _is_s4_filer_is_acquirer --
# the BIDDER_COUNT_ANALYSIS.md swap-and-keep follow-up found the
# filing's own FORM TYPE (a new cache-key input, see below) is a
# sturdier signal than proposal-text "acquire" language for the same
# filer-is-acquirer shape: an S-4's filer is, by SEC rule, always the
# securities-issuing party (the acquirer), full stop, no textual
# evidence needed at all. v7: guarded _is_s4_filer_is_acquirer against
# _is_reverse_merger_text -- without it, a blanket S-4-means-exclude
# rule wrongly re-excluded Movano/Corvex, this module's own canonical
# example of a reverse merger deliberately kept in stats elsewhere
# (and 7 other SPAC-shell-named filers with the same shape). v8:
# replaced _is_s4_filer_is_acquirer (filer identity) with a vote-based
# test -- _is_s4_vote_based_reversed/_is_merger_of_equals/
# _is_s4_buyer_side_only_vote, reading whose named party's own
# shareholders are shown adopting the merger agreement vs. approving a
# share issuance -- after filer identity wrongly excluded 37 deals
# whose S-4 was actually a joint proxy capturing the real target's own
# shareholder vote (Amazon/Globalstar, Rocket Pharmaceuticals/
# Renovacor, PotlatchDeltic/CatchMark, Raymond James/TriState Capital
# among them). _S4_VOTE_MANUAL_OVERRIDES preserves the hand-confirmed
# outcome for the ~15 deals this text-only rule can't safely derive on
# its own (tender/exchange-offer and written-consent approvals, a SPAC
# business-combination vote, a lowercase-first-letter brand name
# ["ironSource"] _NAME_RUN can never capture, three complex/tangled
# structures -- a divestiture, a split-off+merger, a holdco
# reorganization -- excluded without further untangling, and two
# genuinely undetermined deals). v15 (round-4 spot check): renamed
# _is_s4_merger_of_equals to _is_merger_of_equals and widened its gate
# from S-4-only to also accept DEFM14A/PREM14A joint proxies (a genuine
# merger of equals is routinely disclosed that way with no S-4 involved
# at all -- AvalonBay/Equity Residential, Veeco/Axcelis), and added
# Vista Outdoor as a new complex_structure manual override (a Sporting
# Products sale to CSG combined with a Revelyst separation, not a plain
# single-buyer sale). Every classification rule change needs a bump
# here, or a deal keeps silently serving its stale result forever even
# once the rule that should catch it is fixed.
_CLASSIFY_CACHE_VERSION = "v15"


def _classify_cache_key(
    slug: str, target: str, acquirer: str, events: list[dict], proposals: list[dict], form_type: Optional[str]
) -> str:
    relevant_events = [{"event_type": e.get("event_type"), "parties": e.get("parties")} for e in events]
    # v4's _is_proposal_direction_reversed reads proposer + source_quotes
    # -- the only two proposal fields any check here reads -- so those
    # (and only those) join events in the cache key, same reasoning as
    # relevant_events above.
    relevant_proposals = [
        {"proposer": p.get("proposer"), "source_quotes": p.get("source_quotes")} for p in proposals
    ]
    payload = json.dumps(
        {
            "version": _CLASSIFY_CACHE_VERSION,
            "target": target,
            "acquirer": acquirer,
            "events": relevant_events,
            "proposals": relevant_proposals,
            "form_type": form_type,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _classify_cache_path(slug: str, key: str) -> Path:
    return _CLASSIFY_CACHE_DIR / f"{slug}_{key}.json"

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
# "spin-off of X to Y's stockholders" -- unlike the bare word "spin-off"
# (deliberately not matched above, see this section's comment), this
# requires the parent-distributes-subsidiary-TO-its-own-shareholders
# structure spelled out as its own object + recipient, same precision
# as _DISTRIBUTION_RE's "distribution of a stake in" phrasing just
# without the word "distribution" itself (IAC's own board discussion
# of "a spin-off of Vimeo to IAC's stockholders" never uses that word).
# Scoped (?i:...) around the connector words only, not a blanket
# re.IGNORECASE on the whole pattern (see _SHARED_MANAGER_NAMED_RE's
# comment on why that's unsafe for the [A-Z] name-capture groups). "'s"
# matches either apostrophe style, since filing HTML commonly uses the
# curly Unicode one (U+2019), not the ASCII one.
_SPIN_OFF_OF_TO_RE = re.compile(
    r"(?i:spin-?off)\s+of\s+" + r"([A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,4})" + r"\s+to\s+"
    r"([A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,4})" + r"['’]?s?\s+(?i:stockholders|shareholders)\b"
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

# "a reverse merger of X into Y" -- the accounting-classification
# phrasing an S-4/proxy uses when a new holding company (X's new
# surviving-parent shell) is being interposed above an existing public
# company via merger (FTAI/FTAI Finance Holdco Ltd., Mobile
# Infrastructure Corp/Trust). Unlike the bare "reverse merger" phrase
# (flagged but kept IN stats elsewhere, since a real reverse merger --
# Movano/Corvex -- is still a genuine sale, just one where the "target"
# ends up in control), "of X into Y" names the two parties directly, so
# it's checked against target/acquirer below rather than trusted alone.
_REVERSE_MERGER_OF_INTO_RE = re.compile(
    r"\breverse merger of\s+" + _NAME_RUN + r"\s+into\s+" + _NAME_RUN,
    re.IGNORECASE,
)
# "X had/has an approximate NN% ownership interest in Y" -- LXP already
# owning ~99% of LCIF before "merging" with it is the same self
# -reorganization as a holdco interposition, just the opposite
# direction (parent reabsorbing its own already-majority-owned
# affiliate instead of a new holdco being interposed above the
# existing public company).
# Not re.IGNORECASE (see _SHARED_MANAGER_NAMED_RE's comment) -- besides
# the same name-capture-runs-backwards-into-lowercase-prose bug, on a
# multi-megabyte filing IGNORECASE here made this pattern catastrophically
# slow (4+ seconds on one 7MB filing alone, from how many more positions
# [A-Z] now has to try matching against), not just wrong.
_MAJORITY_OWNERSHIP_INTEREST_RE = re.compile(
    r"([A-Z][\w&'\-]*(?:\s+[A-Z][\w&'\-]*){0,4})\s+(?:had|has)\s+an?\s+approximate(?:ly)?\s+"
    r"(\d{1,3})%\s+ownership\s+interest\s+in\s+" + _NAME_RUN
)

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


_CURATED_RAW_DIR = Path("data/raw")


def _curated_html_path(slug: str) -> Optional[Path]:
    """A curated deal's own proxy, already fetched and cached on disk by
    a prior `python -m src.fetch`/`fetch_defm14a` run (data/raw/*.html +
    its sidecar manifest) -- never fetched here, only read. Resolved by
    matching the curated deal's own stored `target` against each
    manifest's "company" field (fuzzy, via is_same_entity) rather than
    re-deriving fetch.py's own filename-slugging convention a second
    time, which has no guaranteed relationship to DEALS's own target
    spelling and could silently drift out of sync with it."""
    from src.run import DEALS

    if slug not in DEALS:
        return None
    target = DEALS[slug]["target"]
    for manifest_path in _CURATED_RAW_DIR.glob("*_defm14a.manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        company = manifest.get("company")
        if company and is_same_entity(company, target):
            html_path = manifest_path.with_name(manifest_path.name.replace(".manifest.json", ".html"))
            if html_path.exists():
                return html_path
    return None


@lru_cache(maxsize=None)
def _full_text(slug: str) -> str:
    cache_path = _parsed_text_cache_path(slug)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    parsed = _bulk_slug_to_cik_accession(slug)
    if parsed is not None:
        html = load_cached_html(*parsed)
    else:
        curated_path = _curated_html_path(slug)
        html = curated_path.read_text(encoding="utf-8", errors="replace") if curated_path else None
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def _is_spin_off(slug: str, target: str, acquirer: str) -> bool:
    text = _full_text(slug)
    if _RMT_RE.search(text) or _DISTRIBUTION_RE.search(text):
        return True
    for m in _SPIN_OFF_OF_TO_RE.finditer(text):
        _spinco, parent = m.group(1).strip(), m.group(2).strip()
        if _is_same_entity_fuzzy(parent, target) or _is_same_entity_fuzzy(parent, acquirer):
            return True
    return False


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

# A direct admission, in the filing's own words, that both sides of the
# merger share one external manager/adviser -- catches affiliated-BDC
# mergers with no adviser-suffixed party in the signing event at all
# (FSK/FSKR's signing event names only the two funds themselves, never
# "FS/KKR Advisor, LLC"). Two phrasings ("GBDC and GBDC 3 have the same
# investment adviser"; "FSK and FSKR are managed by the Advisor"), both
# requiring the TWO NAMES to be captured directly in the same sentence
# -- NOT a bare "we have the same Manager" (an externally managed REIT/
# BDC's routine conflicts-of-interest risk factor, comparing itself to
# OTHER unrelated vehicles under the same sponsor, not confirming
# anything about THIS deal's own target/acquirer) -- so the caller can
# still verify the captured names actually ARE this deal's target/
# acquirer before trusting it. Deliberately not re.IGNORECASE: under
# IGNORECASE, [A-Z] also matches lowercase, which let the name capture
# run backwards into the preceding lowercase prose instead of stopping
# at the real company name.
_SHORT_NAME_RUN = r"([A-Z][\w\d&'\-]*(?:\s+[A-Z0-9][\w\d&'\-]*){0,3})"
_SHARED_MANAGER_NAMED_RE = re.compile(
    _SHORT_NAME_RUN + r"\s+and\s+" + _SHORT_NAME_RUN
    + r"\s+(?:have|has|are|share)\b[^.]{0,40}\b(?:the\s+same\s+)?(?:external\s+)?(?:investment\s+)?(?:adviser|advisor|manager)\b"
)
_MANAGED_BY_SAME_RE = re.compile(
    _SHORT_NAME_RUN + r"\s+and\s+" + _SHORT_NAME_RUN
    + r"\s+(?:are|is)\s+managed\s+by\s+(?:the\s+)?(?:same\s+)?(?:[Aa]dvisor|[Aa]dviser|[Mm]anager)\b"
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
    text = _full_text(slug)
    if _shared_sponsor_brand(text, target, acquirer):
        return True
    # Catches cases with no adviser-suffixed signing party to match at
    # all (FS KKR Capital Corp. II / FSK -- the signing event's parties
    # are just ["FSK", "FSKR"], with "FS/KKR Advisor, LLC" never named
    # as a signer, only elsewhere in the proxy's own text): a direct
    # admission, in the filing's own words, that both NAMED sides share
    # one external manager. At least one of the two captured names must
    # still fuzzy-match target/acquirer -- the sentence structure alone
    # isn't enough (an externally managed REIT/BDC's own TOC/boilerplate
    # can coincidentally satisfy either regex with two unrelated defined
    # terms, e.g. Fortress Transportation's "Affiliates and Affiliated
    # Entities Our Parent is managed by the Manager").
    for rx in (_SHARED_MANAGER_NAMED_RE, _MANAGED_BY_SAME_RE):
        for m in rx.finditer(text):
            a, b = m.group(1).strip(), m.group(2).strip()
            if _is_same_entity_fuzzy(a, target) or _is_same_entity_fuzzy(a, acquirer):
                return True
            if _is_same_entity_fuzzy(b, target) or _is_same_entity_fuzzy(b, acquirer):
                return True
    return False


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


# "<name> ... to acquire <name2>" / "... for the acquisition of <name2>"
# / "... acquisition of <name2>", optionally with a "100% of the
# equity of"/"all of the (issued and) outstanding shares/stock/equity/
# membership interests of/in" object-phrase in between -- the common
# shapes a Background-of-the-Merger narrative uses when naming WHO is
# acquiring WHOM, independent of whether the sentence is first-person
# (_FIRST_PERSON_BUYER_RE, the filer's own voice) or ordinary third
# -person prose. Scoped (?i:...) around the connector words only, same
# reason as _SPIN_OFF_OF_TO_RE: a blanket IGNORECASE would let the
# [A-Z]-anchored _NAME_RUN capture run backward into lowercase prose.
_ACQUIRE_OBJECT_RE = re.compile(
    r"(?i:(?:to|would|will)\s+acquire|for the acquisition of|acquisition of)\s+"
    r"(?i:(?:all(?:\s+of)?|100%\s+of)\s+(?:the\s+)?(?:issued\s+and\s+)?(?:outstanding\s+)?"
    r"(?:shares|stock|equity|membership\s+interests)\s+(?:of|in)\s+)?" + _NAME_RUN
)


# A negated/contrastive frame right before the match ("a combination of
# the companies RATHER THAN an acquisition of X") rejects X-direction as
# the deal's structure instead of asserting it -- ReShape/Obalon's own
# early term sheet uses exactly this phrasing, and without this guard
# the match is read backwards (as if it affirmed what it's actually
# denying).
_NEGATED_ACQUIRE_RE = re.compile(r"(?:rather than|instead of|as opposed to|unlike)\s+(?:an?|the)?\s*$", re.IGNORECASE)


def _is_proposal_direction_reversed(slug: str, target: str, acquirer: str, proposals: list[dict]) -> bool:
    """True when a Proposal's own STRUCTURED proposer field (never
    re-derived from prose subject-extraction, which is much harder to
    get right reliably than reading a field we already trust elsewhere
    in this pipeline) is the stored target, and that same proposal's own
    quote says it's "to acquire"/"for the acquisition of" a name
    matching the stored acquirer -- the filer (always recorded as
    target, see _is_filer_reversed's docstring) is the one proposing to
    acquire the OTHER side, not the other way around (Aon/NFP: "Aon
    delivered...a proposal to acquire 100% of the equity of NFP" --
    proposer="Aon plc"=target, captured="NFP"=acquirer). Unlike
    _is_filer_reversed, this ALSO reads already-extracted proposals data
    every deal has (curated included), not just cached filing HTML
    (bulk-only) -- closing the gap this module's own docstring already
    calls out ("a curated deal is given neither check").

    Also folds in the SAME "X will become a wholly owned subsidiary of
    Y" evidence _is_filer_reversed itself already reads from the full
    text, in both directions: Desktop Metal/Stratasys and ReShape/Obalon
    both had an EARLY, non-binding proposal pointing one way (Desktop
    Metal once proposed to acquire Stratasys; ReShape's own term sheet
    text, read without this, looked like it proposed acquiring Obalon),
    but the deal's own FINAL, legally operative merger-agreement recital
    settles the structure the OTHER way for both -- without weighing
    that stronger, later signal, an early superseded offer alone would
    wrongly flag an already-correctly-labeled deal.

    Airtight like _is_filer_reversed: requires at least one
    reversal-direction signal AND zero signals anywhere in the deal
    asserting the opposite direction -- rejected the weaker "which side
    proposes more" heuristic for the same reason _is_filer_reversed's
    own docstring already rejected it (an ordinary target-shops-itself
    negotiation has the target sending plenty of its own counters too)."""
    reversed_evidence = False
    normal_evidence = False
    for p in proposals:
        proposer = p.get("proposer")
        if not proposer:
            continue
        text = " ".join(p.get("source_quotes") or [])
        for m in _ACQUIRE_OBJECT_RE.finditer(text):
            if _NEGATED_ACQUIRE_RE.search(text[: m.start()]):
                continue
            acquired_name = m.group(1).strip()
            if _is_same_entity_fuzzy(proposer, target) and _is_same_entity_fuzzy(acquired_name, acquirer):
                reversed_evidence = True
            elif _is_same_entity_fuzzy(proposer, acquirer) and _is_same_entity_fuzzy(acquired_name, target):
                normal_evidence = True
    for m in _SUBSIDIARY_OF_RE.finditer(_full_text(slug)):
        child, parent = m.group(1).strip(), m.group(2).strip()
        if _is_same_entity_fuzzy(child, target) and _is_same_entity_fuzzy(parent, acquirer):
            normal_evidence = True
        elif _is_same_entity_fuzzy(child, acquirer) and _is_same_entity_fuzzy(parent, target):
            reversed_evidence = True
    return reversed_evidence and not normal_evidence


# Replaces _is_s4_filer_is_acquirer (v7): that rule treated an S-4's
# filer as ALWAYS the acquirer, by SEC registrant rule -- true in
# general, but wrong for the common STOCK-DEAL shape where the S-4 is
# a JOINT proxy statement/prospectus serving the TARGET's own
# shareholder vote (the registrant still has to register the new
# shares it's issuing, but that doesn't mean its own shareholders are
# the only ones voting). Re-checking by filer identity alone wrongly
# excluded 37 deals -- Amazon/Globalstar, Rocket Pharmaceuticals/
# Renovacor, PotlatchDeltic/CatchMark, and Raymond James Financial/
# TriState Capital among them -- where the Background section narrates
# exactly the real target's sale process this pipeline exists to
# measure. The sturdier test: whose shareholders actually VOTE on
# what, read directly from the filing's own "<Name> stockholders ...
# adopt the Merger Agreement" (or "... of <Name>'s Special Meeting")
# vote-notice language, vs. "<Name> stockholders ... approve the
# issuance"/"Stock Issuance Proposal" (the OTHER standard heading, an
# acquirer paying with its own new stock, not evidence anyone's being
# bought out).
#
# "<Name> stockholders/shareholders/unitholders" in either word order
# a filing uses -- most say "GNB shareholders will be asked to...",
# but some invert it ("SPECIAL MEETING OF UNITHOLDERS ... of NexPoint
# Hospitality Trust"). Scoped (?i:...) around the suffix word only, not
# a blanket re.IGNORECASE -- see _SPIN_OFF_OF_TO_RE's comment on why
# that's unsafe for _NAME_RUN's [A-Z]-anchored capture.
_VOTER_BEFORE_RE = re.compile(r"\b" + _NAME_RUN + r"['’]?s?\s+(?i:stockholders|shareholders|unitholders)\b")
_VOTER_AFTER_RE = re.compile(r"\b(?i:stockholders|shareholders|unitholders)\s+(?i:of)\s+" + _NAME_RUN)
# Two-stage, not a single flat window (tried first): find the FIRST
# adopt/approve verb shortly after the subject, then look for the
# merger-agreement object shortly after THAT verb. A single wide
# window let a DIFFERENT subject's own clear vote bleed into this
# one's: "Unity stockholders approve the issuance of shares ... in
# connection with the merger AND ironSource shareholders approve THE
# MERGER AGREEMENT" is one sentence covering both parties' separate
# proposals, and a flat 300-char search from "Unity stockholders"
# found ironSource's "approve the merger agreement" and wrongly
# attributed it to Unity. Anchoring the object-search to the position
# right after Unity's OWN nearest verb ("approve the issuance...")
# fixes this, since that verb's own 60-char object window only
# contains "the issuance ... in connection with the merger", not
# "Merger Agreement"/"Company Merger"/"Merger Proposal".
_VOTE_VERB_RE = re.compile(r"\b(?:adopt|approve)(?:ed|s|ing)?\b", re.IGNORECASE)
# Deliberately NOT a bare "the Merger" alternative (tried first) --
# too generic a filler reference to the overall transaction to prove
# THIS verb's object is the merger agreement itself, not an ancillary
# share issuance "in the Merger"/"in connection with the Merger".
_MERGER_OBJECT_RE = re.compile(
    r"\b(?:Agreement\s+and\s+Plan\s+of\s+Merger|Merger\s+Agreement|Company\s+Merger|Merger\s+Proposal)",
    re.IGNORECASE,
)
_SUBJECT_TO_VERB_CHARS = 150
_VERB_TO_OBJECT_CHARS = 60


def _adopt_merger_match(text: str, start: int) -> bool:
    """True if the first adopt/approve verb within _SUBJECT_TO_VERB_CHARS
    chars after `start` (a voter-subject match's end) has a merger
    -agreement object within _VERB_TO_OBJECT_CHARS chars after the verb,
    stopping at the first comma/semicolon -- without that, "approve
    the Unity issuance proposal, and if the merger agreement is
    terminated by..." let a later clause's unrelated "merger
    agreement" (the object of "terminated," not "approve") bleed into
    this verb's own object window."""
    near = text[start : start + _SUBJECT_TO_VERB_CHARS]
    verb = _VOTE_VERB_RE.search(near)
    if not verb:
        return False
    obj_window = near[verb.end() : verb.end() + _VERB_TO_OBJECT_CHARS]
    clause_boundary = re.search(r"[,;]", obj_window)
    if clause_boundary:
        obj_window = obj_window[: clause_boundary.start()]
    return bool(_MERGER_OBJECT_RE.search(obj_window))
# "approve the issuance"/"Stock(s) Issuance Proposal" -- the other
# standard proxy heading: a vote only about the acquirer paying with
# its own new stock.
_ISSUANCE_VOTE_WINDOW_RE = re.compile(
    r"\bapprov(?:e|ed|ing|al)\b[^.]{0,40}\bissuance\b|\b(?:Stock|Share)s?\s+Issuance\s+Proposal\b", re.IGNORECASE
)
# "no vote ... is required"/"absence of any required vote"/"not
# required to obtain" -- a closing-condition representation that NO
# vote is needed from this party, the exact opposite of a real vote.
# Checked in the text immediately BEFORE a voter-subject match (that's
# where this phrasing places the negation: "the absence of any
# required vote of the PotlatchDeltic stockholders to approve the
# Company Merger" -- PotlatchDeltic's own closing-condition
# representation that IT needs no vote, not evidence it has one).
# Without this guard, _has_adopt_merger_vote wrongly fired for
# PotlatchDeltic (the real acquirer) and AeroClean (approved by
# written consent, not a vote, per the same "no vote ... is required"
# phrasing) off this exact negated construction.
_NO_VOTE_REQUIRED_RE = re.compile(
    r"\b(?:no|without\s+any)\s+(?:vote|approval)\b[^.]{0,80}\bis\s+required\b|"
    r"absence\s+of\s+any\s+required\s+vote|not\s+required\s+to\s+(?:obtain|seek)\b|"
    # "advisable to, and in the best interests of, X and X's
    # stockholders, [the Board] adopted and approved the merger
    # agreement" -- a BOARD fiduciary recitation ("X's stockholders" is
    # the OBJECT of "in the best interests of," not the subject of
    # "adopted"), not a stockholder vote notice.
    r"(?:advisable\s+to|in\s+the\s+best\s+interests?\s+of)\b|"
    # "proposal to adjourn or postpone any meeting of X ... if there
    # are not sufficient votes to approve the adoption of the merger
    # agreement" -- a procedural adjournment proposal referencing the
    # OVERALL transaction's adoption in passing, not evidence X's OWN
    # shareholders are the ones adopting it (this boilerplate is
    # typically mirrored for both parties' meetings in a joint proxy).
    # Without both guards, _has_adopt_merger_vote wrongly fired for
    # Unity (ironSource/Unity) off this exact boilerplate.
    r"adjourn|postpone",
    re.IGNORECASE,
)
_MERGER_OF_EQUALS_RE = re.compile(r"\bmerger of equals\b(?!\s*\(as defined)", re.IGNORECASE)
_VOTE_WINDOW_CHARS = 300
_NEGATION_LOOKBACK_CHARS = 150


def _voter_subjects(text: str) -> list[tuple[str, int, int]]:
    """Every "<Name> stockholders"/"stockholders of <Name>" match in
    `text`, as (name, match-start, match-end) -- match-end is where the
    caller looks for adopt/issuance language, in a short window
    immediately following; match-start is where it looks BACKWARD for
    a "no vote is required" negation immediately preceding the name."""
    subjects = [(m.group(1).strip(), m.start(), m.end()) for m in _VOTER_BEFORE_RE.finditer(text)]
    subjects += [(m.group(1).strip(), m.start(), m.end()) for m in _VOTER_AFTER_RE.finditer(text)]
    return subjects


def _has_adopt_merger_vote(text: str, name: str) -> bool:
    for subject, start, end in _voter_subjects(text):
        if not _is_same_entity_fuzzy(subject, name):
            continue
        if _NO_VOTE_REQUIRED_RE.search(text[max(0, start - _NEGATION_LOOKBACK_CHARS) : start]):
            continue
        if _adopt_merger_match(text, end):
            return True
    return False


def _has_issuance_only_vote(text: str, name: str) -> bool:
    found_issuance = False
    for subject, start, end in _voter_subjects(text):
        if not _is_same_entity_fuzzy(subject, name):
            continue
        if _NO_VOTE_REQUIRED_RE.search(text[max(0, start - _NEGATION_LOOKBACK_CHARS) : start]):
            continue
        if _adopt_merger_match(text, end):
            return False
        if _ISSUANCE_VOTE_WINDOW_RE.search(text[end : end + _VOTE_WINDOW_CHARS]):
            found_issuance = True
    return found_issuance


# Slug-keyed overrides for deals this investigation confirmed by hand
# but that the generalizable vote-text rule above can't safely derive
# on its own -- either because the real party's approval is a tender/
# exchange offer or a private company's written consent (neither reads
# as "stockholders ... adopt the Merger Agreement"), or because the
# vote direction genuinely can't be determined from this filing's text
# at all. `target`/`acquirer` were already corrected to their real
# names for the "include" cases (see the one-time correction applied
# alongside this rule change), so this dict only needs to record the
# INCLUDE/EXCLUDE outcome, not a name fix. "exclude" for the
# undetermined deals (MaxLinear, Smucker/Hostess) preserves their
# PRIOR (excluded) status, per instruction, rather than defaulting
# them to newly-included just because no textual signal was found
# either way. "complex_structure" is its own, distinct outcome for
# deals whose structure is genuinely tangled (a divestiture to a
# third-party buyer entity, a split-off combined with a merger, a
# holdco reorganization with no real second party) -- per instruction,
# these are excluded with their own reason and NOT worth further
# untangling.
_S4_VOTE_MANUAL_OVERRIDES: dict[str, str] = {
    # Marel hf. shareholders approve via a voluntary public takeover
    # offer (>=90% tendering, or less with Marel's own consent) under
    # Icelandic/EU takeover rules, not a Delaware-style adoption vote;
    # JBT's own shareholders vote only on JBT's Share Issuance Proposal.
    "bulk_1433660_000119312524139600": "include",
    # MGP approved by written consent of its own members, not a formal
    # special-meeting vote; VICI's own shareholders vote only on the
    # VICI Stock Issuance Proposal.
    "bulk_1705696_000119312521267902": "include",
    # Northern Data Shareholders approve via the Exchange/Takeover
    # Offer and become Rumble stockholders on settlement; Rumble's own
    # "adopt the Business Combination Agreement" vote is Rumble's own
    # required acquirer-side approval, not a target-side vote.
    "bulk_1830081_000121390026042803": "include",
    # Wolt's board approved the Share Purchase Agreement, and ALL Wolt
    # shareholders approved by written consent -- a private company's
    # approval mechanism, not a public special-meeting vote.
    "bulk_1792789_000119312521365019": "include",
    # ironSource's own shareholders approve via a merger proposal under
    # Israeli Companies Law Section 320; Unity's own shareholders vote
    # only on Unity's Issuance Proposal. Not derivable by the general
    # rule above: "ironSource" is stylized with a lowercase first
    # letter, so it can never match _NAME_RUN's [A-Z]-anchored capture
    # -- a brand-stylization gap in the generalized rule, not a
    # judgment call about the vote itself.
    "bulk_1810806_000114036122027456": "include",
    # SPAC-shape "Business Combination": only BT Brands' own ("Pubco")
    # stockholders vote to adopt the Merger Agreement -- a structural
    # SPAC requirement regardless of deal direction -- and no separate
    # Aero shareholder vote is described anywhere in the filing.
    "bulk_1718224_000147793225009283": "exclude",
    # AeroClean's own shareholders vote only on approving the stock
    # -issuance merger consideration; zero described approval
    # mechanism (vote, tender, or consent) found for Molekule anywhere
    # in the filing -- same shape as Bally's/Gamesys and Mesa/
    # Republic, not Wolt/MGP's explicit written consent.
    "bulk_1872356_000110465922128138": "exclude",
    # Undetermined: only generic "Parent Board"-calls-special-meeting
    # procedural language found; no deal-specific vote evidence for
    # either stored party despite extensive searching.
    "bulk_1288469_000110465922071588": "exclude",
    # Undetermined: despite 1,214 mentions of "Hostess," zero vote
    # -process language found for either party -- this S-4 appears to
    # discuss the (already-closed, cash-tender) Hostess acquisition
    # only as financial/business background, not as this filing's own
    # live merger-proxy narrative.
    "bulk_91419_000119312523253048": "exclude",
    # Complex structure, not worth untangling further: Aquarion is
    # ALREADY Eversource's own subsidiary per the filing text, and a
    # third entity "NESC" (New England Service Company) is the one
    # whose stockholders vote -- this reads as a multi-step
    # reorganization/divestiture-shaped transaction, not a plain
    # arm's-length sale.
    "bulk_72741_000110465921076935": "complex_structure",
    # Complex structure, not worth untangling further: a combined
    # split-off+merger (Liberty Media splits off its Liberty SiriusXM
    # tracking stock and merges it into the separate "Sirius XM
    # Holdings," a third entity named in the one merger-adoption vote
    # found, matching neither stored field).
    "bulk_2003397_000110465924007830": "complex_structure",
    # Complex structure, not worth untangling further: "Twin Vee Inc."
    # is a new holding company interposed above the existing "Twin Vee
    # Co."; Forza X1 is Twin Vee Co.'s own existing EV-boat subsidiary,
    # not a separate merger counterparty -- a holdco reorganization
    # with no real second party to resolve the stored acquirer field
    # "Unknown" to.
    "bulk_1855509_000173112222001537": "complex_structure",
    # Complex structure, not worth untangling further (round-4 spot
    # check): a sale of Vista Outdoor's Sporting Products Business to
    # CSG, combined with a separation/distribution of its OTHER
    # business (Revelyst) to Vista's own existing shareholders -- not a
    # plain sale of the whole company to a single buyer. The stored
    # acquirer field ("MNC") is a rival, unsolicited, never-signed
    # proposal for the whole company, not the real counterparty (CSG)
    # to the actual signed transaction.
    "bulk_1616318_000162828024014367": "complex_structure",
}


def _is_s4_vote_based_reversed(slug: str, target: str, acquirer: str, form_type: Optional[str]) -> bool:
    """True when the ACQUIRER field's own named party -- not the
    target field's -- is the one whose shareholders are shown adopting
    the merger agreement, i.e. target/acquirer are reversed for this
    S-4."""
    if form_type != "S-4":
        return False
    text = _full_text(slug)
    if _has_adopt_merger_vote(text, target):
        return False
    return _has_adopt_merger_vote(text, acquirer)


# A genuine merger of equals is disclosed via several form types, not
# just an S-4 (which only applies when new securities are being
# registered) -- AvalonBay/Equity Residential and Veeco/Axcelis are
# both DEFM14A joint proxy statements, with no S-4 involved at all,
# and both explicitly call themselves a "merger of equals" in their own
# text. A tender offer (SC 14D9/SC TO-T) is deliberately excluded: that
# structure is inherently one party buying out the other's shares for
# cash/stock, never a genuine combination of equals, so the phrase
# wouldn't legitimately appear as a real structural description there.
_MERGER_OF_EQUALS_FORM_TYPES = {"S-4", "DEFM14A", "PREM14A"}


def _is_merger_of_equals(slug: str, target: str, acquirer: str, form_type: Optional[str]) -> bool:
    """True when the filing calls itself a "merger of equals" (Hut 8/
    USBTC, Steel Newco/Pinnacle, Ballston Spa/NBC, AvalonBay/Equity
    Residential, Veeco/Axcelis). Deliberately NOT "both target's and
    acquirer's own shareholders are shown adopting the merger
    agreement" (tried first) -- a dual shareholder vote is an ordinary
    STATUTORY requirement for plenty of ordinary (not merger-of-equals)
    bank-holding-company and REIT mergers where one side is clearly the
    acquirer (LINKBANCORP/GNB, Mesa Air Group/Republic, Ready Capital/
    Broadmark), so that alone wrongly flagged nine real swap/acquisition
    deals as merger-of-equals."""
    if form_type is not None and form_type not in _MERGER_OF_EQUALS_FORM_TYPES:
        return False
    return bool(_MERGER_OF_EQUALS_RE.search(_full_text(slug)))


def _is_s4_buyer_side_only_vote(slug: str, target: str, acquirer: str, form_type: Optional[str]) -> bool:
    """True when NEITHER party has a found merger-adoption vote, and
    at least one of them votes on a share issuance only -- i.e. only
    the real acquirer's shareholders have a described vote at all
    (Bally's/Gamesys, Drilling Tools/DTI, AeroVironment)."""
    if form_type != "S-4":
        return False
    text = _full_text(slug)
    if _has_adopt_merger_vote(text, target) or _has_adopt_merger_vote(text, acquirer):
        return False
    return _has_issuance_only_vote(text, target) or _has_issuance_only_vote(text, acquirer)


# "each of X and Y will become a wholly owned subsidiary of Z" -- a
# double-dummy/new-HoldCo merger-of-equals structure (Apollo/Athene:
# "each of Athene and Apollo will become a wholly owned subsidiary of
# Tango Holdings") where NEITHER existing company absorbs the other;
# both get subordinated to a brand-new third entity. Distinct from
# _is_self_reorganization's holdco-interposition check (which requires
# BOTH captured names to already be this deal's own target/acquirer --
# a parent reabsorbing its OWN pre-existing affiliate), since here the
# new HoldCo is a THIRD name matching neither, and only ONE of the two
# merging companies needs to match target/acquirer -- the other is
# often the deal's real counterparty under a name our own acquirer
# field never correctly captured (AHL special committee, not "Athene
# Holding Ltd.", for Apollo/Athene).
_EACH_OF_SUBSIDIARY_RE = re.compile(
    r"(?i:each of)\s+" + _NAME_RUN + r"(?i:\s+and\s+)" + _NAME_RUN
    + r"(?i:\s+will\s+become\s+an?\s+(?:indirect,?\s+)?wholly[- ]owned\s+subsidiary\s+of\s+)" + _NAME_RUN
)


def _is_new_holdco_merger(slug: str, target: str, acquirer: str) -> bool:
    text = _full_text(slug)
    for m in _EACH_OF_SUBSIDIARY_RE.finditer(text):
        name1, name2, newco = (g.strip() for g in m.groups())
        if _is_same_entity_fuzzy(newco, target) or _is_same_entity_fuzzy(newco, acquirer):
            continue
        if (
            _is_same_entity_fuzzy(name1, target)
            or _is_same_entity_fuzzy(name2, target)
            or _is_same_entity_fuzzy(name1, acquirer)
            or _is_same_entity_fuzzy(name2, acquirer)
        ):
            return True
    return False


def _acquirer_is_target_governance_body(target: str, acquirer: str) -> bool:
    """True when the stored acquirer field is just a reference to the
    TARGET's OWN board/special/conflicts committee ("SST VI Special
    Committee" when target IS "Strategic Storage Trust VI, Inc.",
    "SRT Special Committee" when target IS "Sunrise Realty Trust,
    Inc." -- "SRT" a literal acronym of it) -- not an independent
    second party at all, so there is no real acquirer name here to
    resolve, swap in, or ever display; a discovery-time labeling
    defect, not a reversed-but-resolvable pair (contrast
    _is_filer_reversed/_is_proposal_direction_reversed, where the real
    acquirer DOES have a usable name, just stored in the wrong field).
    A bare governance term with no subject at all ("Conflicts
    Committee", no company name attached) is treated the same way --
    the only entity in scope for an unqualified "the Committee" to be
    negotiating on behalf of is this deal's own target. Deliberately
    does NOT fire when the subject names a DIFFERENT real company
    (e.g. "Hudson Special Committee" when target is "STAR EQUITY
    HOLDINGS, INC." -- no name relationship at all, so "Hudson" is
    someone else's committee, an unresolved acquirer-display problem,
    not a target/acquirer mislabeling one)."""
    if not is_governance_body_reference(acquirer):
        return False
    subject = governance_body_subject(acquirer)
    if subject is None:
        return True
    return _is_same_entity_fuzzy(subject, target)


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


def _is_self_reorganization(slug: str, target: str, acquirer: str) -> bool:
    """True when target and acquirer are each other's own pre-existing
    affiliate -- a holding company being interposed above an existing
    public company via merger (FTAI Finance Holdco Ltd., formed as an
    indirect subsidiary of FTAI before "acquiring" it in a holdco
    merger) or a parent reabsorbing its own already-majority-owned
    operating partnership (LXP Industrial Trust already owning ~99% of
    LCIF before "merging" with it) -- never an arm's-length sale to an
    independent third party, regardless of how the bare "reverse
    merger"/"reorganization" words alone would otherwise classify it
    (those stay included elsewhere: a real reverse merger, like Movano/
    Corvex, is still a genuine sale)."""
    text = _full_text(slug)
    for m in _REVERSE_MERGER_OF_INTO_RE.finditer(text):
        merged_away, surviving_parent = m.group(1).strip(), m.group(2).strip()
        # BOTH sides must independently match target/acquirer -- a
        # single-match requirement let through a real false positive:
        # Cherry Hill/TPG Mortgage's "reverse merger of Party A with and
        # into CHMI" is an ordinary competitive THIRD-PARTY bidder
        # ("Party A", an anonymized placeholder, one of several real
        # bidders -- Party B, Party D -- in a genuine process run by
        # BTIG) proposing a reverse-merger STRUCTURE, not an affiliate
        # relationship; "CHMI" alone matching our stored acquirer
        # trivially, with no check on the OTHER name, wrongly excluded
        # a real sale. Requiring both sides narrows out this and
        # Boundless Bio/Serapha (an ordinary reverse-merger-structured
        # third-party acquisition, the exact scenario the plain
        # reverse_merger category -- Movano/Corvex -- already handles
        # correctly) while still catching FTAI Finance Holdco Ltd. (both
        # "FTAI" and "FTAI Finance Holdco Ltd." resolve to this deal's
        # own target).
        if (_is_same_entity_fuzzy(merged_away, target) or _is_same_entity_fuzzy(merged_away, acquirer)) and (
            _is_same_entity_fuzzy(surviving_parent, target) or _is_same_entity_fuzzy(surviving_parent, acquirer)
        ):
            return True
    for m in _MAJORITY_OWNERSHIP_INTEREST_RE.finditer(text):
        owner, pct, owned = m.group(1).strip(), int(m.group(2)), m.group(3).strip()
        if pct < 50:
            continue
        owner_is_party = _is_same_entity_fuzzy(owner, target) or _is_same_entity_fuzzy(owner, acquirer)
        owned_is_party = _is_same_entity_fuzzy(owned, target) or _is_same_entity_fuzzy(owned, acquirer)
        if owner_is_party and owned_is_party:
            return True
    return False


def classify_deal(
    slug: str, target: str, acquirer: str, events: list[dict], proposals: list[dict], form_type: Optional[str] = None
) -> tuple[str, bool, Optional[str]]:
    """Disk-cached wrapper around _classify_deal_uncached -- see
    _CLASSIFY_CACHE_DIR's comment for the cache key and invalidation
    rationale. `proposals` has no default -- an old call site missed
    during the v4 wiring fails loudly (TypeError) rather than silently
    losing _is_proposal_direction_reversed coverage. Every real caller
    (src.bulk_stats, src.deal_metrics) already has `d["proposals"]`
    sitting next to the `d["events"]` it passes. `form_type` DOES
    default (to None, meaning "unknown/curated") -- a curated deal has
    no `deal_candidates` row to read one from at all, and treating that
    absence as "not an S-4" (rather than failing loudly) is correct,
    not a silently-lost check the way a missing `proposals` would be."""
    key = _classify_cache_key(slug, target, acquirer, events, proposals, form_type)
    cache_path = _classify_cache_path(slug, key)
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        return cached["deal_type"], cached["excluded_from_stats"], cached["exclusion_reason"]

    result = _classify_deal_uncached(slug, target, acquirer, events, proposals, form_type)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"deal_type": result[0], "excluded_from_stats": result[1], "exclusion_reason": result[2]}),
        encoding="utf-8",
    )
    return result


def _classify_deal_uncached(
    slug: str, target: str, acquirer: str, events: list[dict], proposals: list[dict], form_type: Optional[str]
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
    manager's contract), self-reorganization (target and acquirer are
    each other's own pre-existing affiliate -- a holdco interposition
    or a parent reabsorbing its own operating partnership), then
    filer-reversal (the filer is reported acquiring/absorbing someone
    else, not being bought out itself). reverse_merger is flagged but
    never excludes -- it's still a real sale process, just one where
    the legal "acquirer" ends up controlled by the legal "target"'s
    former owners."""
    if _is_spin_off(slug, target, acquirer):
        return (
            "spin_off",
            True,
            "spin-off / parent distribution of a subsidiary stake to its own shareholders, not an arm's-length sale process",
        )
    if _is_self_reorganization(slug, target, acquirer):
        return (
            "self_reorganization",
            True,
            "target and acquirer are each other's own pre-existing affiliate (a holdco interposition or a parent reabsorbing its own operating partnership), not an arm's-length sale process",
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
    if _is_merger_of_equals(slug, target, acquirer, form_type):
        return "merger_of_equals", False, None
    s4_override = _S4_VOTE_MANUAL_OVERRIDES.get(slug)
    if s4_override == "complex_structure":
        return (
            "complex_structure",
            True,
            "a divestiture to a third-party buyer entity, a split-off combined with a merger, or a holdco reorganization with no real second party -- genuinely tangled, not a plain arm's-length sale process",
        )
    if s4_override == "exclude":
        return (
            "buyer_side_s4_vote",
            True,
            "only the acquirer's own shareholders have a described approval mechanism for this S-4, or the vote direction can't be determined from this filing's text at all",
        )
    if s4_override != "include":
        if (
            _is_filer_reversed(slug, target, acquirer)
            or _is_proposal_direction_reversed(slug, target, acquirer, proposals)
            or _is_s4_vote_based_reversed(slug, target, acquirer, form_type)
        ):
            return (
                "filer_is_acquirer",
                True,
                "the filer (recorded here as target) is actually the acquirer, or is absorbing a third party -- target/acquirer are reversed or mislabeled for this deal",
            )
        if _is_s4_buyer_side_only_vote(slug, target, acquirer, form_type):
            return (
                "buyer_side_s4_vote",
                True,
                "only the acquirer's own shareholders have a described vote (on a share issuance) for this S-4 -- no vote, tender, or consent evidence found for the real target's own shareholders",
            )
    if _is_new_holdco_merger(slug, target, acquirer):
        return (
            "new_holdco_merger_of_equals",
            True,
            "a double-dummy merger where both target and acquirer become subsidiaries of a brand-new third holding company, not a traditional single-acquirer sale process",
        )
    if _acquirer_is_target_governance_body(target, acquirer):
        return (
            "acquirer_is_target_governance_body",
            True,
            "the stored acquirer field is just a reference to the target's own board/special/conflicts committee, not an independent second party -- no real acquirer name is available for this deal",
        )
    if _is_reverse_merger_text(slug):
        return "reverse_merger", False, None
    return "acquisition", False, None
