"""Headline stats across canonical deals (deals.is_canonical, after
src.dedup_deals has run -- both curated and bulk-discovered rows,
whichever one is each transaction's canonical representative).

    python -m src.bulk_stats

Mirrors the established conventions in apps/web/src/lib/dealSummary.ts
(nBidders, firstBidProposal/finalBidProposal via price_high ?? price_low
and accepted-else-last-dated) rather than inventing new definitions,
except where this task's own spec is explicitly narrower (percent
-increase is restricted to cash deals with both prices, which
dealSummary.ts's pctChange does not do), adds data-quality filtering
dealSummary.ts doesn't need (that code runs over hand-curated, reviewed
deals; this runs over ~1000 unreviewed extractions, where a stray
near-zero first price or a misdated event can produce a nonsense
outlier -- see the thresholds below), or is deliberately stricter:
daysFirstContactToSigning here requires a real first_contact event and
is excluded (not backfilled from the earliest dated event of any kind)
when there isn't one, since dealSummary.ts's own fallback was found to
both understate some deals' real process length and fabricate a date
for others with no usable first-contact signal at all.

Target-side placeholder terms ("the Company", "Target", "Board", etc.)
are resolved to each deal's own target name before any proposer/
recipient comparison via src.entity_match.is_same_entity, not exact
string equality -- extracted text uses informal short names ("Knoll")
that never exactly match EDGAR's raw legal name ("KNOLL INC").

Per-deal compute_*_for_deal functions are the single source of truth
for both this module's aggregate stats AND src.deal_metrics's
per-deal row -- a deal's exclusion reason (and often its raw computed
value, even when excluded) is returned alongside the value so
deal_metrics can store exactly what each aggregate used or skipped,
instead of recomputing a second, possibly-drifting copy of the same
logic. When this module runs standalone it also refreshes both DB
metrics tables (src.deal_metrics.refresh_all) and the JSON file.
"""

import json
import re
import statistics
from datetime import date
from pathlib import Path
from typing import Optional

import psycopg

from src import validate
from src.dedup_deals import _is_generic
from src.entity_match import _is_ticker_of, core_name, is_acronym_of, is_anonymized_placeholder, is_governance_body_reference, is_same_entity
from src.env import load_env
from src.load_db import connect

load_env()

PROMPT_LOCK_PATH = Path("config/prompt_lock.json")

CONTACT_EVENT_TYPES = {"first_contact", "nda", "discussion"}
N_OUTLIERS = 10

# Data-quality thresholds for the two stats most exposed to a single bad
# extracted number (a near-zero first price, or a misdated event).
# Excluded deals are listed by reason, never silently dropped.
MIN_FIRST_PRICE_USD = 0.10
MIN_FIRST_PRICE_PCT_OF_FINAL = 0.05
MAX_ABS_PCT_CHANGE = 300.0
MAX_DAYS_FOR_REVIEW = 2000
REVIEW_PCT_DROP_THRESHOLD = -90.0


def _resolve_target(name: Optional[str], target: str) -> Optional[str]:
    if name and (
        name.strip().lower() in validate._TARGET_DEFINED_TERMS
        or is_same_entity(name, target)
        or is_acronym_of(name, target)
    ):
        return target
    return name


def _load_prompt_lock_run_dirs() -> dict[str, str]:
    if not PROMPT_LOCK_PATH.exists():
        return {}
    data = json.loads(PROMPT_LOCK_PATH.read_text())
    return {slug: info["run_dir"] for slug, info in data.get("results", {}).items()}


_PROMPT_LOCK_RUN_DIRS = _load_prompt_lock_run_dirs()


def _resolve_run_id_for_deal(conn: psycopg.Connection, deal_id: str, slug: str) -> Optional[str]:
    """Exactly one extraction_runs row per deal, never a sum across
    several -- a curated deal that went through the v8-v12 prompt
    iteration cycle (Splunk, Zendesk) has one extraction_runs row PER
    ITERATION, and joining on deal_id alone (the previous behavior)
    silently summed proposals/events across all of them, inflating
    every count (Splunk showed 43 proposals across 3 runs instead of
    the locked v11 run's real 14). config/prompt_lock.json's own
    run_dir is authoritative when present (it can name an OLDER run
    than the globally "locked_prompt_version" -- e.g. Splunk's locked
    run is explicitly v11, not v12, because v12 only added unrelated
    functionality and v11's validated result stands). Otherwise falls
    back to the most recently started run, which is a no-op for the
    ~1123 deals that only ever had exactly one run anyway."""
    if slug in _PROMPT_LOCK_RUN_DIRS:
        row = conn.execute(
            "SELECT id FROM extraction_runs WHERE deal_id = %s AND run_dir = %s",
            (deal_id, _PROMPT_LOCK_RUN_DIRS[slug]),
        ).fetchone()
        if row:
            return row[0]
    row = conn.execute(
        "SELECT id FROM extraction_runs WHERE deal_id = %s ORDER BY started_at DESC LIMIT 1",
        (deal_id,),
    ).fetchone()
    return row[0] if row else None


def _fetch_canonical_deals(conn: psycopg.Connection) -> list[dict]:
    """Canonical deals, further excluding any that src.classify_deal_type
    flags as not a genuine arm's-length sale process (a spin-off, an
    affiliated-manager merger, or a filer/target reversal) -- these
    stay in the deals/deal_metrics tables and on their own deal page,
    but never feed a cross-deal aggregate (parties contacted, bidders,
    days to signing...), which would otherwise mix a handful of
    structurally different transactions into stats meant to describe
    ordinary competitive sale processes."""
    from src.classify_deal_type import classify_deal

    deals = fetch_deals(conn, canonical_only=True)
    return [
        d for d in deals
        if not classify_deal(d["slug"], d["target"], d["acquirer"], d["events"], d["proposals"], d["form_type"])[1]
    ]


def fetch_deals(conn: psycopg.Connection, canonical_only: bool = False) -> list[dict]:
    """Like _fetch_canonical_deals, but canonical_only=False also
    returns non-canonical deals (deal_id included) -- src.deal_metrics
    needs a row for every deal, not just the canonical ones used in
    aggregates."""
    from src.classify_deal_type import _bulk_slug_to_cik_accession

    query = "SELECT d.id, d.slug, d.deal_name, d.target, d.acquirer FROM deals d"
    if canonical_only:
        query += " WHERE d.is_canonical"
    rows = conn.execute(query).fetchall()
    # Keyed by (cik, accession-with-dashes) to join against each bulk
    # deal's own discovery-time form type -- None for a curated deal
    # (no deal_candidates row at all) rather than guessed.
    form_type_by_accession = dict(conn.execute("SELECT primary_accession, primary_form_type FROM deal_candidates").fetchall())
    deals = []
    for deal_id, slug, deal_name, target, acquirer in rows:
        parsed_cik_accession = _bulk_slug_to_cik_accession(slug)
        form_type = form_type_by_accession.get(parsed_cik_accession[1]) if parsed_cik_accession else None
        run_id = _resolve_run_id_for_deal(conn, deal_id, slug)
        if run_id is None:
            events, proposals = [], []
        else:
            events = conn.execute(
                """
                SELECT e.date_start, e.event_type, e.parties, e.summary, e.source_quotes
                FROM events e
                WHERE e.run_id = %s AND e.passed
                """,
                (run_id,),
            ).fetchall()
            proposals = conn.execute(
                """
                SELECT p.date_resolved, p.proposer, p.recipient, p.price_low, p.price_high,
                       p.consideration_type, p.status, p.source_quotes
                FROM proposals p
                WHERE p.run_id = %s AND p.passed
                """,
                (run_id,),
            ).fetchall()
        deals.append(
            {
                "deal_id": deal_id,
                "slug": slug,
                "deal_name": deal_name,
                "target": target,
                "acquirer": acquirer,
                "form_type": form_type,
                "events": [
                    {
                        "date_start": e[0],
                        "event_type": e[1],
                        "parties": [_resolve_target(p, target) for p in (e[2] or [])],
                        "summary": e[3],
                        "source_quotes": e[4] or [],
                    }
                    for e in events
                ],
                "proposals": [
                    {
                        "date_resolved": p[0],
                        "proposer": _resolve_target(p[1], target),
                        "recipient": _resolve_target(p[2], target),
                        "price_low": float(p[3]) if p[3] is not None else None,
                        "price_high": float(p[4]) if p[4] is not None else None,
                        "consideration_type": p[5],
                        "status": p[6],
                        "source_quotes": p[7] or [],
                    }
                    for p in proposals
                ],
            }
        )
    return deals


def _dated_proposals(proposals: list[dict]) -> list[dict]:
    dated = [p for p in proposals if p["date_resolved"] is not None]
    dated.sort(key=lambda p: p["date_resolved"])
    return dated


def _price(p: dict) -> Optional[float]:
    return p["price_high"] if p["price_high"] is not None else p["price_low"]


def _final_entry(dated: list[dict]) -> Optional[dict]:
    accepted = [p for p in dated if p["status"] == "accepted"]
    if accepted:
        return accepted[-1]
    return dated[-1] if dated else None


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None}
    sorted_values = sorted(values)
    if len(values) >= 4:
        q1, _, q3 = statistics.quantiles(sorted_values, n=4, method="inclusive")
    else:
        q1 = q3 = statistics.median(sorted_values)
    return {
        "min": sorted_values[0],
        "p25": q1,
        "median": statistics.median(sorted_values),
        "p75": q3,
        "max": sorted_values[-1],
    }


# --- per-deal computations (shared with src.deal_metrics) --------------------


def compute_n_parties_contacted_for_deal(d: dict) -> int:
    contacted = {
        name
        for e in d["events"]
        if e["event_type"] in CONTACT_EVENT_TYPES
        for name in e["parties"]
        if name and name != d["target"]
    }
    return len(contacted)


# A proposal for less than the whole target -- a minority stake, a
# reinsurance arrangement, specific assets or operations, a licensing
# deal, or a strategic (non-controlling) investment rather than the
# company itself -- doesn't make its proposer a bidder FOR the target,
# however real the proposer is otherwise (Midwest Holding's "Party G"
# proposed a $7.2M minority investment plus reinsuring a portion of the
# business, not to acquire the company).
_PARTIAL_PROPOSAL_RE = re.compile(
    r"\breinsur|\bminority (?:stake|interest|investment)\b|"
    r"\b(?:certain|specific) assets\b|\basset[- ]only\b|"
    r"\b(?:certain|specific) (?:operations|businesses|business units)\b|"
    r"\blicens(?:e|ing)\b|\bstrategic investment\b",
    re.IGNORECASE,
)

# A bare honorific-plus-personal-name proposer ("Mr. Greisch", "Dr. Avi
# Katz") is virtually always an officer/director communicating on
# behalf of a real corporate bidder (Catalent: "Mr. Greisch" ->
# "Novo Parties" is Catalent's own officer relaying a message, not a
# rival bid from an individual), not itself a company capable of
# acquiring the whole target -- dropped from the bidder count
# regardless of which side of the deal they're associated with.
_INDIVIDUAL_NAME_RE = re.compile(
    r"^(?:Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Messrs\.?|Prof\.?)\s+[A-Z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)*$"
)


def _is_individual_name(name: str) -> bool:
    return bool(_INDIVIDUAL_NAME_RE.match(name.strip()))

# Splits a joint-bid proposer string ("Company A and Consortium B",
# "Advent, Permira and Crosspoint") into its constituent bidders, so
# each one is counted once -- as itself, merged with any proposal where
# it bid alone -- instead of the whole joint-bid string ALSO counting
# as if it were yet another, different bidder (United States Steel's
# n_bidders included "Company A", "Consortium B", AND "Company A and
# Consortium B" as three separate bidders for what both already-counted
# singly). Guarded by requiring every resulting part to look like a
# proper name (starts upper-case or a digit) -- a non-joint-bid phrase
# that merely contains the word "and" ("a third-party financial
# partner", "management of Terra BDC and TPT") usually has at least one
# part that doesn't, and is left unsplit rather than exploded into
# fragments.
_LEGAL_SUFFIX_WORDS = r"inc\.?|incorporated|corp\.?|corporation|llc|l\.l\.c\.?|lp|l\.p\.?|ltd\.?|limited|plc|co\.?|company"
# The comma in "Fertitta Entertainment, Inc." is part of ONE company's
# own name, not a list separator -- splitting there produced a real
# "Inc." fragment bidder. Matches filing_party_names._CONNECTOR_SPLIT_RE's
# same negative lookahead for exactly this reason.
_JOINT_PROPOSER_SPLIT_RE = re.compile(r",\s*(?!(?:" + _LEGAL_SUFFIX_WORDS + r")\b)|\s+and\s+")


def _split_joint_proposer(name: str) -> list[str]:
    cleaned = re.sub(r",\s*and\s+", ", ", name)
    parts = [p.strip() for p in _JOINT_PROPOSER_SPLIT_RE.split(cleaned) if p.strip()]
    if len(parts) <= 1:
        return [name]
    if not all(p[0].isupper() or p[0].isdigit() for p in parts):
        return [name]
    return parts


def _add_bidder(bidders: set[str], name: str) -> None:
    """Adds `name` unless an already-added bidder is the same entity
    under a different formality level or a short-form alias -- splitting
    a joint bid can otherwise reintroduce the exact over-count it's
    meant to fix: a deal naming "Nippon Paint and Sherwin-Williams" in
    one proposal and "Nippon Paint Holdings Co., Ltd and The
    Sherwin-Williams Company" in another would split into 4 strings for
    what are really 2 bidders. is_acronym_of (checked both directions,
    since either the acronym or the full name could already be in the
    set) catches an initials-style alias the same way -- "FEI" and
    "Fertitta Entertainment, Inc." are the same bidder, not two
    (Caesars/Fertitta).

    Skipped entirely for an anonymized placeholder ("Party A", "Party
    AA") -- is_same_entity's prefix-match logic treats "Party A" as a
    match for "Party AA" (the longer core name literally starts with
    the shorter one), which would silently merge two of a heavily
    -shopped deal's genuinely distinct anonymized bidders into one
    (AVROBIO's 40+ Party-lettered bidders lost more than half under this
    before the guard)."""
    if is_anonymized_placeholder(name):
        bidders.add(name)
        return
    for existing in bidders:
        if is_anonymized_placeholder(existing):
            continue
        if is_same_entity(name, existing) or is_acronym_of(name, existing) or is_acronym_of(existing, name):
            return
    bidders.add(name)


def _is_unusable_fragment(name: str) -> bool:
    """True for a string that's never a real bidder no matter what --
    empty, a bare corporate-suffix fragment left over from a bad split
    ("Inc.", "LLC" with nothing else -- core_name strips the suffix and
    whatever's left is empty), or a bare individual's name (see
    _is_individual_name). Checked unconditionally, even for the deal's
    own eventual acquirer -- unlike a generic ROLE term (see
    _is_non_bidder_role), which the eventual acquirer is exempted from,
    there's no sense in which a lone "Inc." fragment or an officer's
    name IS the acquirer, however it got attached to an accepted
    proposal."""
    if not name or not core_name(name):
        return True
    return _is_individual_name(name)


def _is_non_bidder_role(name: str) -> bool:
    """True for a name that's a role/defined-term placeholder rather
    than a specific company capable of acquiring the whole target --
    the target's own board/committee (see is_governance_body_reference),
    a generic role term like "Sellers" (the defined term for a group of
    selling shareholders in a carve-out/JV transaction, negotiating on
    the SELL side, not a rival bidder trying to acquire the target --
    Bunge/Viterra's "Sellers" responding with a counterproposal is the
    divesting shareholder group talking back, not a competing offer) or
    "Investor"/"Parent"/"Buyer" (see dedup_deals._GENERIC_ACQUIRER_TERMS,
    the same generic-placeholder list used to decide an acquirer name
    is unusable). Exempted for the deal's own eventual acquirer (see
    compute_n_bidders_for_deal) -- several deals only ever call their
    real, eventual acquirer "Parent" throughout their own extracted
    text, and excluding it here would silently drop the actual winning
    bidder from the count entirely."""
    return is_governance_body_reference(name) or _is_generic(name)


def _is_same_company_fuzzy(name: str, other: str) -> bool:
    """True when `name` plausibly refers to the same company as
    `other`, including under a ticker/short-name (WMC, BNCC) rather
    than its literal stored legal name -- a plain string-equality check
    misses these. Used both to recognize the target bidding for itself
    under an alias, and to recognize a proposer as the deal's own
    stored acquirer under a generic term never otherwise resolved."""
    return name == other or is_same_entity(name, other) or is_acronym_of(name, other) or _is_ticker_of(name, other)


def compute_n_bidders_for_deal(d: dict) -> int:
    """The eventual acquirer (d["acquirer"], the deal's own stored
    acquirer field -- not re-derived from whichever proposal happens to
    be marked "accepted", since that marker sometimes lands on the
    TARGET's own counter-proposal in a late-stage back-and-forth, e.g.
    Dawson/Wilks's accepted entry has proposer="Company" with
    recipient="Parent") is always counted as a bidder if it made any
    proposal, even when its own raw name is a generic term never
    otherwise resolved in this deal's extracted text (Dawson/Wilks and
    Bio-Techne/Merck both only ever call their real, eventual acquirer
    "Parent" throughout -- excluding every "Parent"-named proposer as
    non-bidder-role, with no exemption, silently dropped the actual
    winning bidder from the count entirely)."""
    target = d["target"]
    acquirer = d["acquirer"]

    bidders: set[str] = set()
    for p in d["proposals"]:
        proposer = p.get("proposer")
        if not proposer or _is_same_company_fuzzy(proposer, target) or _is_unusable_fragment(proposer):
            continue
        is_eventual_acquirer = _is_same_company_fuzzy(proposer, acquirer)
        if _is_non_bidder_role(proposer) and not is_eventual_acquirer:
            continue
        if _PARTIAL_PROPOSAL_RE.search(" ".join(p.get("source_quotes") or [])):
            continue
        for name in _split_joint_proposer(proposer):
            if _is_same_company_fuzzy(name, target) or _is_unusable_fragment(name):
                continue
            if _is_non_bidder_role(name) and not is_eventual_acquirer:
                continue
            _add_bidder(bidders, name)
    return len(bidders)


def compute_n_proposals_for_deal(d: dict) -> int:
    return len(d["proposals"])


def _proposals_not_extracted_counts(n_proposals: int, n_bidders: int) -> bool:
    """True when a deal has zero Proposal records at all -- never because
    there were truly no bids (every deal has at least an eventual
    acquirer who signed something), but because this run's extraction
    produced no Proposal record for the deal's Background of the Merger
    section at all (Twitter/Musk, New Relic, Skillsoft/Codecademy)."""
    return n_proposals == 0 and n_bidders == 0


def _proposals_not_extracted(d: dict) -> bool:
    return _proposals_not_extracted_counts(compute_n_proposals_for_deal(d), compute_n_bidders_for_deal(d))


def compute_first_final_price_for_deal(d: dict) -> tuple[Optional[float], Optional[float]]:
    """First dated proposal's price and the final (accepted, else
    latest-dated) proposal's price -- independent of the stricter cash/
    threshold rules compute_pct_bump_for_deal applies, so a deal can
    have a determinable first/final price here even when it's excluded
    from the % bump stat itself (e.g. the final proposal isn't cash)."""
    dated = _dated_proposals(d["proposals"])
    if not dated:
        return None, None
    first_price = _price(dated[0])
    final = _final_entry(dated)
    final_price = _price(final) if final else None
    return first_price, final_price


def compute_final_price_range_for_deal(d: dict) -> tuple[Optional[float], Optional[float]]:
    """The final entry's raw (price_low, price_high) -- distinct from
    compute_first_final_price_for_deal's single combined final_price,
    needed to tell a genuine single price (price_low == price_high)
    apart from a quoted range (price_low != price_high)."""
    dated = _dated_proposals(d["proposals"])
    final = _final_entry(dated)
    if final is None:
        return None, None
    return final["price_low"], final["price_high"]


# Matches a dollar amount in a quote's own text ("$74.00", "$1.25 per
# share", "C$1.48"/"A$0.90" -- a currency-code prefix before the "$" is
# fine, only the digits after it matter here).
_DOLLAR_AMOUNT_RE = re.compile(r"\$\s*([\d,]+\.?\d*)")


def _is_dollar_denominated(price: float, quotes: list[str]) -> bool:
    """True if a consideration_type='stock' proposal's own source
    quote confirms its stored price is a genuine dollar-per-share
    figure -- an "implied value of $X per share" is a real, common
    convention even for an all-stock deal (Mr. Cooper/Rocket: $154.00;
    Renovacor/Rocket: "an implied value of $2.10 per share") -- rather
    than a bare exchange ratio with no dollar amount mentioned
    anywhere in its own quote at all ("a fixed exchange ratio of
    0.3575x", Axcelis/Veeco). A plain magnitude threshold can't tell
    these apart -- genuine ratios (commonly 0.3-2.5) and genuine
    per-share dollar prices for a lower-priced stock (Sonnet/Rorschach:
    $1.25; Home Point: $1.80) overlap in exactly the same range --
    so this checks the quote's own text for the stored number spelled
    out with a leading "$", not just its size."""
    for m in _DOLLAR_AMOUNT_RE.finditer(" ".join(quotes)):
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if abs(amount - price) < 0.015:
            return True
    return False


def compute_final_price_is_ratio_for_deal(d: dict) -> Optional[bool]:
    """True when the final price should be displayed as a stock
    -exchange ratio, not a dollar amount -- the final proposal's
    consideration_type is 'stock' AND its own source quotes never
    spell out the stored number as a dollar figure (see
    _is_dollar_denominated). None when there's no final price at all;
    False (show as a dollar price) for every other consideration_type,
    since a spot-check confirmed cash/mixed/unknown deals in this
    dataset always store a genuine stated per-share dollar price."""
    dated = _dated_proposals(d["proposals"])
    final = _final_entry(dated)
    if final is None:
        return None
    price = _price(final)
    if price is None:
        return None
    if final.get("consideration_type") != "stock":
        return False
    return not _is_dollar_denominated(price, final.get("source_quotes") or [])


def compute_pct_bump_for_deal(d: dict) -> tuple[Optional[float], Optional[str]]:
    """Returns (pct, exclusion_reason). reason is None exactly when pct
    is a valid, includable value. For abs_change_over_300pct, pct still
    carries the (excluded) computed value -- useful for a diagnostic
    listing of what got excluded and why; every other exclusion reason
    means pct couldn't be computed at all, so it's None."""
    dated = _dated_proposals(d["proposals"])
    if len(dated) < 2:
        return None, "fewer_than_2_dated_proposals"
    final = _final_entry(dated)
    if final is None or final["consideration_type"] != "cash":
        return None, "not_cash_or_no_final"
    first_price = _price(dated[0])
    final_price = _price(final)
    if first_price is None:
        return None, "missing_first_price"
    if final_price is None:
        return None, "missing_final_price"
    if final_price <= 0:
        return None, "final_price_non_positive"
    if first_price == 0 or first_price < MIN_FIRST_PRICE_USD:
        return None, "first_price_below_10_cents"
    if first_price < MIN_FIRST_PRICE_PCT_OF_FINAL * abs(final_price):
        return None, "first_price_below_5pct_of_final"
    pct = (final_price - first_price) / first_price * 100
    if abs(pct) > MAX_ABS_PCT_CHANGE:
        return pct, "abs_change_over_300pct"
    return pct, None


def pct_bump_bucket(pct: Optional[float]) -> Optional[str]:
    """Histogram bucket label for a % bump value, width 10 (e.g. "0% to
    10%", "-10% to 0%"), with an overflow bucket above 100%. None input
    (not computed, or excluded) yields None, not a bucket -- a consumer
    must check pct_bump_exclusion_reason to tell "excluded" apart from
    "genuinely in a bucket"."""
    if pct is None:
        return None
    if pct > 100:
        return ">100%"
    lower = int(pct // 10) * 10
    return f"{lower}% to {lower + 10}%"


def _normalize_bidder_name(name: str, acquirer: str) -> str:
    """A generic/shell term ("Merger Sub", "Parent", "Consortium"...,
    see dedup_deals._GENERIC_ACQUIRER_TERMS) always refers to THIS
    deal's own acquirer in an ordinary (non-reversed) deal -- the same
    substitution compute_n_bidders_for_deal already relies on via its
    own eventual-acquirer exemption (see _is_non_bidder_role). Applying
    it here too lets two different shell aliases for the SAME real
    party (a consortium calling itself "Consortium" in early letters,
    then signing as its own newly formed "Merger Sub") compare equal,
    instead of looking like two different companies."""
    return acquirer if _is_generic(name) else name


def compute_first_bidder_won_for_deal(d: dict) -> tuple[Optional[bool], Optional[str]]:
    dated = _dated_proposals(d["proposals"])
    # Excluding only the LITERAL target string misses two shapes
    # compute_n_bidders_for_deal already screens out: the target's own
    # negotiating body under a different name (a "Conflicts
    # Committee"/"the Board"/"Strategic Review Committee" responding to
    # a bidder's offer is the target's own side talking back, not a
    # second bidder -- exempted only for the deal's own eventual
    # acquirer, on the rare chance a committee name ended up stored as
    # the acquirer field itself), and a proposal for less than the
    # whole target (a minority stake, a reinsurance arrangement, ... --
    # see _PARTIAL_PROPOSAL_RE's own docstring -- its proposer isn't
    # bidding FOR the target at all, however real it otherwise is).
    bidder_dated = [
        p
        for p in dated
        if p["proposer"]
        and p["proposer"] != d["target"]
        and not (is_governance_body_reference(p["proposer"]) and not _is_same_company_fuzzy(p["proposer"], d["acquirer"]))
        and not _PARTIAL_PROPOSAL_RE.search(" ".join(p.get("source_quotes") or []))
    ]
    if not bidder_dated:
        return None, "no_non_target_proposal"
    # Picking "final" from bidder_dated (not the full `dated` list) is
    # the exact same target-exclusion compute_n_bidders_for_deal already
    # applies -- without it, a target's own counter-offer or mirrored
    # confirmation (marked accepted, or just latest-dated) gets credited
    # as "the winning bid" (Verint: the accepted entry is literally
    # Verint's own willingness-to-accept communicated through its
    # advisor, not Thoma Bravo's).
    final = _final_entry(bidder_dated)
    if final is None or not final["proposer"]:
        return None, "no_final_entry"
    first_bidder = _normalize_bidder_name(bidder_dated[0]["proposer"], d["acquirer"])
    eventual_acquirer = _normalize_bidder_name(final["proposer"], d["acquirer"])
    return _is_same_company_fuzzy(first_bidder, eventual_acquirer), None


# A first_contact event with no deal-relevant language at all ("became
# acquainted...spoke periodically during 2018") is a social
# introduction, not first contact ABOUT acquiring or combining with the
# target (Support.com/Greenidge: the real first_contact that led to the
# merger is three years later, in 2021) -- required only for
# first_contact events, since a 'proposal'-typed event or an actual
# Proposal record already IS, by definition, about acquiring the
# target and needs no further relevance check.
_DEAL_RELEVANT_CONTACT_RE = re.compile(
    r"\bacqui\w*|\bmerg\w*|\bcombin\w*|\btransaction\w*|\bpropos\w*|"
    r"\bstrategic\b|\bsale process\b|\bpotential (?:sale|deal)\b|"
    r"\bsubsidiary\b|\bpartnership\w*|\bsynerg\w*",
    re.IGNORECASE,
)


def _is_deal_relevant_contact(summary: Optional[str]) -> bool:
    return bool(summary and _DEAL_RELEVANT_CONTACT_RE.search(summary))


def _process_start_date(d: dict):
    """The deal's earliest contact or proposal, by ANY party, about
    acquiring or combining with the target -- not just a literal
    first_contact-typed event (Catalent: Party A's December 2022
    proposal letter is earlier contact than Party B's January 2023
    first_contact event, and only counting the latter understated the
    real process length). Candidates are a first_contact event that
    actually mentions a deal (see _is_deal_relevant_contact -- a purely
    social introduction doesn't count), any proposal-typed event, or
    any row in the deal's own Proposal records (covers an extraction
    that only produced an Event, never a matching Proposal row, for
    the same underlying offer). Deliberately NOT a fallback to the
    earliest event/proposal of ANY kind -- a board meeting, an
    unrelated asset sale, or a public announcement still isn't contact
    about this deal. Callers treat None as "no process-start date,"
    excluding the deal from timing stats rather than ever guessing."""
    candidates = []
    for e in d["events"]:
        if not e["date_start"]:
            continue
        if e["event_type"] == "proposal":
            candidates.append(e["date_start"])
        elif e["event_type"] == "first_contact" and _is_deal_relevant_contact(e.get("summary")):
            candidates.append(e["date_start"])
    for p in d.get("proposals", []):
        if p.get("date_resolved"):
            candidates.append(p["date_resolved"])
    return min(candidates) if candidates else None


# Deliberately narrow and unambiguous: every one of these is, in every
# deal structure this pipeline has seen, a financing-side or
# shareholder-support document, never the deal's own operative
# agreement. Left OUT on purpose: "exchange agreement", "investment
# agreement", "subscription agreement", "letter of intent" -- each of
# those names the ACTUAL definitive agreement for some deal structures
# (a share-exchange deal's "Exchange Agreement"; Cyclacel/Fitters) and
# including them produced real false exclusions.
_ANCILLARY_DOC_RE = re.compile(
    r"\b(voting agreement|support agreement|guaranty|guarantee|"
    r"equity commitment letter|debt commitment letter|commitment letter|"
    r"credit agreement)\b",
    re.IGNORECASE,
)
# Deliberately broad: anything that plausibly names a deal's own
# definitive agreement, across the several structures this pipeline
# extracts (merger, equity/asset/stock purchase, share exchange,
# business combination, scheme of arrangement) -- this only has to
# override a false ancillary-only read, not uniquely identify "the"
# document, so a generic "the Agreement" counts too.
_DEFINITIVE_DOC_RE = re.compile(
    r"\b(merger agreement|agreement and plan of merger|plan of merger|"
    r"business combination agreement|transaction agreement|purchase agreement|"
    r"exchange agreement|implementation agreement|scheme of arrangement|"
    r"definitive agreement|the agreement)\b",
    re.IGNORECASE,
)


def _signing_event_text(e: dict) -> str:
    return " ".join([e.get("summary") or ""] + list(e.get("source_quotes") or []))


def _is_ancillary_only_signing(e: dict) -> bool:
    """True when a signing event's own text names only a financing
    -side/support document (see _ANCILLARY_DOC_RE) with no mention of
    anything that could be the deal's own definitive agreement (see
    _DEFINITIVE_DOC_RE) -- Global Business Travel's latest "signing"
    event is a Voting Agreement executed a day after the real Merger
    Agreement, and naively taking the latest-dated signing event picks
    it over the real one. An event that mentions a non-binding
    indication of interest or letter of intent and nothing else matches
    neither regex, so isn't excluded here -- it doesn't need to be:
    a preliminary document always predates the real signing, so taking
    the LATEST surviving event (below) already prefers the real one
    over it without risking a false exclusion on deal structures this
    function doesn't recognize by name."""
    text = _signing_event_text(e)
    return bool(_ANCILLARY_DOC_RE.search(text)) and not bool(_DEFINITIVE_DOC_RE.search(text))


def _latest_signing_date(d: dict):
    """The deal's signing date -- the latest-dated signing event, after
    two filters: (1) drop any signing event dated before every other
    dated event/proposal in the deal, which catches a signing event
    that's actually a completely different, earlier transaction (a
    SPAC's own formation agreement, re-tagged as this deal's signing --
    Renovacor's extracted "signing" is its 2021 SPAC business
    combination, over two months before Rocket ever makes contact); a
    deal can't have signed before its own process began. (2) prefer a
    signing event that mentions the actual merger agreement over one
    that's ancillary-document-only (see _is_ancillary_only_signing) --
    degrades back to the full (pre-filter-2) set if that filter would
    otherwise remove every signing event, since an event that mentions
    neither a merger agreement nor a known ancillary document by name
    is more likely an extraction-phrasing gap than a genuine ancillary
    -only signing, and shouldn't be thrown away. Filter 1 has no such
    fallback -- a deal with zero events/proposals to compare against
    skips it entirely, but a deal where every signing event fails it
    has no signing date at all, rather than ever using a signing event
    that cannot possibly belong to this deal's own process."""
    signings = [e for e in d["events"] if e["event_type"] == "signing" and e["date_start"]]
    if not signings:
        return None

    other_dates = [e["date_start"] for e in d["events"] if e["event_type"] != "signing" and e["date_start"]]
    other_dates += [p["date_resolved"] for p in d.get("proposals", []) if p.get("date_resolved")]
    if other_dates:
        earliest_other = min(other_dates)
        signings = [e for e in signings if e["date_start"] >= earliest_other]
    if not signings:
        return None

    valid = [e for e in signings if not _is_ancillary_only_signing(e)]
    candidates = valid if valid else signings
    return max(e["date_start"] for e in candidates)


def _days_between(start, end) -> int:
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    return (end - start).days


def compute_days_first_contact_to_signing_for_deal(d: dict) -> tuple[Optional[int], Optional[str]]:
    process_start = _process_start_date(d)
    if process_start is None:
        return None, "no_process_start_date"
    signing_date = _latest_signing_date(d)
    if signing_date is None:
        return None, "no_signing_event"
    days = _days_between(process_start, signing_date)
    if days < 0:
        return days, "negative_duration"
    return days, None


def compute_days_first_proposal_to_signing_for_deal(d: dict) -> tuple[Optional[int], Optional[str]]:
    dated = _dated_proposals(d["proposals"])
    if not dated:
        return None, "no_dated_proposal"
    first_proposal_date = dated[0]["date_resolved"]
    signing_date = _latest_signing_date(d)
    if signing_date is None:
        return None, "no_signing_event"
    days = _days_between(first_proposal_date, signing_date)
    if days < 0:
        return days, "negative_duration"
    return days, None


# --- aggregate stats -----------------------------------------------------


def stat_parties_contacted(deals: list[dict]) -> dict:
    values = [compute_n_parties_contacted_for_deal(d) for d in deals]
    return {
        "definition": "Number of distinct non-target parties named in any first_contact, nda, or discussion event for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no such event",
    }


def stat_n_bidders(deals: list[dict]) -> dict:
    values = [compute_n_bidders_for_deal(d) for d in deals]
    return {
        "definition": "Number of distinct non-target proposers across the deal's proposals (parties that actually submitted a priced bid, not just made contact).",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no non-target proposer",
    }


def stat_n_proposals(deals: list[dict]) -> dict:
    values = [compute_n_proposals_for_deal(d) for d in deals]
    return {
        "definition": "Total count of Proposal records (from any proposer, including the target's own counteroffers) extracted for the deal.",
        "n": len(values),
        **_distribution(values),
        "exclusions": "none -- 0 counted for deals with no proposals",
    }


_PCT_BUMP_EXCLUDED_DEAL_REASONS = {
    "final_price_non_positive", "first_price_below_10_cents",
    "first_price_below_5pct_of_final", "abs_change_over_300pct",
}


def stat_pct_increase_cash(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {
        "not_cash_or_no_final": 0, "missing_first_price": 0, "missing_final_price": 0,
        "fewer_than_2_dated_proposals": 0, "first_price_below_10_cents": 0,
        "first_price_below_5pct_of_final": 0, "final_price_non_positive": 0,
        "abs_change_over_300pct": 0,
    }
    excluded_deals = []
    flagged_for_review = []
    for d in deals:
        pct, reason = compute_pct_bump_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            if reason in _PCT_BUMP_EXCLUDED_DEAL_REASONS:
                first_price, final_price = compute_first_final_price_for_deal(d)
                entry = {"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "reason": reason}
                if reason == "abs_change_over_300pct":
                    entry["pct_increase"] = pct
                excluded_deals.append(entry)
            continue
        if pct <= REVIEW_PCT_DROP_THRESHOLD:
            first_price, final_price = compute_first_final_price_for_deal(d)
            flagged_for_review.append({"deal_name": d["deal_name"], "first_price": first_price, "final_price": final_price, "pct_increase": pct})
        values.append((d["deal_name"], pct))

    pct_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Percent change from the earliest dated proposal's price (price_high if present else price_low) to the final (accepted, else latest-dated) proposal's price, restricted to deals whose final proposal is cash and where both prices are known.",
        "n": len(pct_values),
        **_distribution(pct_values),
        "top_outliers": [{"deal_name": name, "pct_increase": v} for name, v in top],
        "flagged_for_review_drop_90pct_or_more": flagged_for_review,
        "exclusions": excluded_counts,
        "excluded_deals": excluded_deals,
    }


def stat_first_bidder_is_acquirer(deals: list[dict]) -> dict:
    matches = 0
    n = 0
    excluded = {"no_non_target_proposal": 0, "no_final_entry": 0}
    for d in deals:
        won, reason = compute_first_bidder_won_for_deal(d)
        if reason is not None:
            excluded[reason] += 1
            continue
        n += 1
        if won:
            matches += 1
    return {
        "definition": "Share of deals where the proposer of the earliest dated non-target proposal is the same (case-insensitive) as the proposer of the final (accepted, else latest-dated) proposal.",
        "n": n,
        "pct_first_bidder_is_eventual_acquirer": (matches / n * 100) if n else None,
        "exclusions": excluded,
    }


def stat_days_first_contact_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {"no_process_start_date": 0, "no_signing_event": 0, "negative_duration": 0}
    flagged_for_review = []
    for d in deals:
        days, reason = compute_days_first_contact_to_signing_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            continue
        if days > MAX_DAYS_FOR_REVIEW:
            flagged_for_review.append({"deal_name": d["deal_name"], "days": days})
        values.append((d["deal_name"], days))

    day_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Days from the deal's earliest first_contact event to its latest signing event. Excluded (not backfilled from any other event type) when no first_contact event was extracted.",
        "n": len(day_values),
        **_distribution(day_values),
        "top_outliers": [{"deal_name": name, "days": v} for name, v in top],
        "flagged_for_review_over_2000_days": flagged_for_review,
        "exclusions": excluded_counts,
    }


def stat_days_first_proposal_to_signing(deals: list[dict]) -> dict:
    values = []
    excluded_counts = {"no_dated_proposal": 0, "no_signing_event": 0, "negative_duration": 0}
    flagged_for_review = []
    for d in deals:
        days, reason = compute_days_first_proposal_to_signing_for_deal(d)
        if reason is not None:
            excluded_counts[reason] += 1
            continue
        if days > MAX_DAYS_FOR_REVIEW:
            flagged_for_review.append({"deal_name": d["deal_name"], "days": days})
        values.append((d["deal_name"], days))

    day_values = [v for _, v in values]
    top = sorted(values, key=lambda t: t[1], reverse=True)[:N_OUTLIERS]
    return {
        "definition": "Days from the deal's earliest dated proposal to its latest signing event -- a cleaner anchor than first_contact, which many deals never extract.",
        "n": len(day_values),
        **_distribution(day_values),
        "top_outliers": [{"deal_name": name, "days": v} for name, v in top],
        "flagged_for_review_over_2000_days": flagged_for_review,
        "exclusions": excluded_counts,
    }


def compute_all() -> dict:
    """Deliberately does NOT include days_first_contact_to_signing --
    a round-3 spot-check found 5 of 9 field errors were first-contact
    dates (the single least reliable extracted signal in the
    pipeline), so this stat is excluded from the public headline_stats
    table and the site entirely. The per-deal value is still computed
    and stored in deal_metrics.days_first_contact_to_signing (see
    src.deal_metrics.compute_metrics_for_deal) -- kept in the database
    as an experimental column, just never surfaced or aggregated
    publicly. days_first_proposal_to_signing is unaffected and remains
    the headline stat for process duration."""
    with connect() as conn:
        deals = _fetch_canonical_deals(conn)
    # bidders/proposals/bump are the only stats that would otherwise
    # count a deal's missing extraction as a real "0" -- parties_
    # contacted doesn't depend on Proposal records at all, and first-
    # bidder/days-to-signing already self-exclude a 0-proposal deal via
    # their own "no proposal to anchor from" reason, same net effect
    # without double-filtering.
    deals_with_proposals = [d for d in deals if not _proposals_not_extracted(d)]
    return {
        "n_canonical_deals": len(deals),
        "parties_contacted": stat_parties_contacted(deals),
        "bidders_who_submitted_a_proposal": stat_n_bidders(deals_with_proposals),
        "proposals_per_deal": stat_n_proposals(deals_with_proposals),
        "pct_increase_cash_deals": stat_pct_increase_cash(deals_with_proposals),
        "pct_first_bidder_is_eventual_acquirer": stat_first_bidder_is_acquirer(deals),
        "days_first_proposal_to_signing": stat_days_first_proposal_to_signing(deals),
    }


def main() -> None:
    from src.deal_metrics import refresh_all

    result = compute_all()
    print(json.dumps(result, indent=2, default=str))
    summary = refresh_all()
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
