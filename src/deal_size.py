"""Deterministic extraction (no LLM) of a deal's size: shares
outstanding as of the record date, and -- only when the filing states
one outright -- an aggregate transaction/equity value. Both are read
straight from the filing's own cached text (src.classify_deal_type.
_full_text), with the exact source sentence kept as a quote, the same
convention every other extracted fact in this pipeline follows.

Works for curated deals too, as long as their own proxy has already
been fetched and cached on disk (src.classify_deal_type._full_text
resolves a curated slug's own data/raw/*.html the same way it resolves
a bulk slug's cached discovery document) -- there's no separate
bulk-only guard here; a slug with nothing cached either way just gets
`_full_text`'s empty string, same as always.

    from src.deal_size import extract_shares_outstanding, extract_aggregate_value, extract_merger_consideration
"""

import re
from typing import Optional

from src.classify_deal_type import _full_text
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

# A "Treatment of Equity Awards" section states option/RSU/warrant
# counts in the exact same "there were N outstanding ___" construction
# extract_shares_outstanding's other keywords all still match (Anaplan:
# "there were 4,425,144 outstanding options to acquire Anaplan common
# stock", "there were 8,947,507 outstanding restricted stock units
# (rights to receive Anaplan shares)") -- neither is the share count
# itself, however closely either sentence otherwise matches the real
# share-count construction (the second one even contains the word
# "shares"). Checked in a window right after the number rather than
# requiring strict adjacency to "shares" -- real share-count sentences
# routinely put a qualifier between the number and "shares"/"stock"
# ("outstanding shares", "Company Common Shares", a bracket-wrapped
# "[2,312,887] shares"), so adjacency alone rejected several genuine
# matches when first tried.
_AWARD_TYPE_RE = re.compile(r"\boptions?\b|\brestricted stock units?\b|\bwarrants?\b|\bRSUs?\b", re.IGNORECASE)
# "Units," not "shares," is the equivalent, unambiguous term an
# LP/MLP's own equity instrument goes by (EnLink Midstream, Oasis
# Midstream, Crestwood -- "457,079,545 outstanding EnLink Units",
# "48,627,680 Oasis Midstream common units outstanding"). Checked
# AFTER _AWARD_TYPE_RE's "restricted stock units" so that phrase still
# correctly excludes, not matches, via this broader word.
_SHARE_WORD_RE = re.compile(r"\bshares?\b|\bstock\b|\bunits?\b", re.IGNORECASE)
_SHARE_COUNT_WINDOW = 60

# Some filings name the award type BEFORE the number instead of after
# ("Confluent options covering an aggregate of 14,828,996 shares of
# our common stock") -- checking only the window after the number, as
# originally written, missed this phrasing and let an options count
# through just because "shares" happened to appear right after it too.
_AWARD_TYPE_BEFORE_WINDOW = 40

# A number introduced as a hypothetical ("for illustrative purposes
# only, assume there are...") is explicitly NOT a stated fact, however
# well it otherwise matches the real share-count construction (Uniti
# Group: an "assume there are 242,443,090 shares...immediately prior
# to Closing" pro-forma example outranked the deal's own actual
# "On the Record Date, there were 244,229,237 Uniti Common Shares
# outstanding" purely by appearing earlier in the document).
_HYPOTHETICAL_RE = re.compile(r"\bassume\b|\billustrative\b|\bhypothetical\b|\bfor example\b", re.IGNORECASE)


def _share_count_candidates(sentence: str) -> list[int]:
    if _HYPOTHETICAL_RE.search(sentence):
        return []
    values = []
    for m in _LARGE_NUMBER_RE.finditer(sentence):
        before = sentence[max(0, m.start() - _AWARD_TYPE_BEFORE_WINDOW) : m.start()]
        after = sentence[m.end() : m.end() + _SHARE_COUNT_WINDOW]
        if _AWARD_TYPE_RE.search(before) or _AWARD_TYPE_RE.search(after):
            continue
        if _SHARE_WORD_RE.search(after):
            values.append(int(m.group(0).replace(",", "")))
    return values


def _sentences_mentioning(text: str, *keywords: str | tuple[str, ...]) -> list[str]:
    """Sentence-like chunks (split on real sentence-ending periods,
    see _SENTENCE_SPLIT_RE) that mention every one of `keywords`,
    case-insensitively -- deliberately not one combined regex, since a
    single [^.]* run can't tell a decimal point from a sentence
    boundary either, the same problem _SENTENCE_SPLIT_RE exists to
    avoid. A keyword given as a tuple is an alternatives group -- ANY
    one of them satisfies that slot (e.g. "record date" or "the filing
    of this proxy statement" are both specific, equally unambiguous
    anchors for a share count, just worded differently)."""

    def _matches(chunk: str, kw: str | tuple[str, ...]) -> bool:
        # A tuple's alternatives are hand-written regex patterns (this
        # module's own); a bare string keyword is literal text and
        # still escaped, exactly as before -- extract_aggregate_value
        # passes a matched dollar-amount string here, which contains
        # real regex metacharacters ("$", ".", parentheses) that must
        # be matched literally, not interpreted.
        if isinstance(kw, tuple):
            return any(re.search(alt, chunk, re.IGNORECASE) for alt in kw)
        return bool(re.search(re.escape(kw), chunk, re.IGNORECASE))

    return [chunk.strip() for chunk in _SENTENCE_SPLIT_RE.split(text) if all(_matches(chunk, kw) for kw in keywords)]


def _names_target(sentence: str, target: str) -> bool:
    """True if `sentence`'s own text contains `target`'s full core
    name. Tried a looser first-word-only fallback (a filing's own
    share-count sentence sometimes refers to a company by just its
    first word, "Pioneer" rather than "Pioneer Energy Services") --
    reverted: across the full bulk population it matched far more
    UNRELATED sentences than it ever correctly resolved, trading a
    handful of real fixes for many new wrong answers. A sentence that
    never names the target at all is still a usable last-resort
    candidate (see the `named or candidates[0]` fallback below)."""
    core = core_name(target)
    return bool(core) and core in core_name(sentence)


def extract_shares_outstanding(slug: str, target: str) -> Optional[dict]:
    """Returns {"value": int, "quote": str} or None. The record-date
    share count, read straight from the filing's own sentence -- never
    computed, inferred, or guessed."""
    text = _full_text(slug)
    if not text:
        return None

    candidates = []
    # "there were"/"there are" (the actual count-statement construction,
    # present tense included -- MIRA: "As of the Record Date, there ARE
    # 19,069,315 shares...") is a required keyword -- "record date" +
    # "outstanding" alone also matches unrelated sentences that just
    # happen to mention both words (Healthpeak/Physicians Realty Trust:
    # "Based upon the number of outstanding shares on the record
    # date... Healthpeak will issue approximately 162,957,213 shares"
    # is about NEW shares issued AS MERGER CONSIDERATION, not either
    # company's own current share count -- it mentions both keywords,
    # but never says "there were"/"there are").
    #
    # The date anchor itself accepts a second, equally specific and
    # unambiguous phrasing some filings use instead of "record date" --
    # a share count stated as of the proxy statement's own filing date
    # (Coupa: "As of the date of the filing of this proxy statement,
    # there were 75,541,300 shares of Company common stock outstanding").
    _DATE_ANCHOR = ("record date", r"(?:date of|filing of) this (?:proxy statement|information statement)")
    _COUNT_VERB = ("there were", "there are")
    for sentence in _sentences_mentioning(text, _DATE_ANCHOR, "outstanding", _COUNT_VERB):
        values = _share_count_candidates(sentence)
        if not values:
            continue
        # The first number in the sentence that passed the award-type
        # filter -- a sentence naming both common and preferred counts
        # ("35,097,821 common shares... and 6,000 preferred shares...")
        # states the common count first.
        value = values[0]
        # A merger-of-equals filing states BOTH companies' own share
        # counts in separate sentences (Healthpeak/Physicians Realty
        # Trust) -- only the one naming this deal's own target is the
        # right count for ITS implied equity value.
        names_target = _names_target(sentence, target)
        # When neither candidate names the target directly (Pioneer
        # Energy Services/Patterson-UTI: Pioneer's own sentence never
        # repeats its name either, just "Pioneer common stock"), prefer
        # one anchored to the literal "record date" -- specific to
        # THIS deal's own shareholder vote -- over the looser "date of
        # this proxy statement" anchor, which just as easily describes
        # a counterparty's own count stated elsewhere in the same
        # joint filing.
        uses_record_date = bool(re.search("record date", sentence, re.IGNORECASE))
        candidates.append((names_target, uses_record_date, value, sentence.strip()))

    if not candidates:
        return None
    named = [c for c in candidates if c[0]]
    pool = named if named else candidates
    record_dated = [c for c in pool if c[1]]
    chosen = record_dated[0] if record_dated else pool[0]
    return {"value": chosen[2], "quote": chosen[3]}


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


# Anchors a candidate sentence on the "you will receive"/"converted
# into the right to receive" construction every merger-consideration
# clause in this dataset uses, worded one of a few equivalent ways.
_RECEIVE_RE = re.compile(
    r"\b(?:will receive|entitled to receive|right to receive|be converted into the right to receive|"
    r"will be converted into|be entitled to receive)\b",
    re.IGNORECASE,
)
# A dollar figure is only a genuine cash-consideration amount, not a
# par-value or an unrelated dollar figure elsewhere in the same
# sentence, when "in cash" follows it within the same clause.
_CASH_AMOUNT_RE = re.compile(r"\$\s*([\d,]+\.\d{2,4})(?=[^.]{0,30}in cash)", re.IGNORECASE)
# "0.840 of a share of ExxonMobil common stock" / "one share of SSTC
# Common Stock" -- a fixed exchange ratio stated as a number of the
# ACQUIRER's shares per target share.
_RATIO_AMOUNT_RE = re.compile(r"([\d]+\.[\d]{2,4})\s+(?:of a )?shares?\s+of\b", re.IGNORECASE)
# A hypothetical/illustrative example ("if you own 100 shares, you will
# receive $420.00") states an ARITHMETIC MULTIPLE of the real per-share
# price, not the price itself (ZAGG: real price $4.20, example $420.00
# for 100 shares) -- same trap deal_size.py's own share-count extractor
# already guards against (see _HYPOTHETICAL_RE above) for a different
# field.
_HYPOTHETICAL_RE = re.compile(r"\bassume\b|\billustrative\b|\bhypothetical\b|\bfor example\b|\bif you own\b", re.IGNORECASE)
# An equity-award (option/RSU/PSU/warrant) cash-out formula reads just
# like a real per-share consideration sentence but prices a DIFFERENT
# instrument under its own separate conversion formula (Aris: RSU/PSU
# payouts use "the product of (i) the total number of shares..."), not
# the deal's own common-stock merger consideration.
_AWARD_RE = re.compile(r"\boptions?\b|\brestricted stock units?\b|\bwarrants?\b|\bRSUs?\b|\bPSUs?\b|\bequity awards?\b", re.IGNORECASE)


def extract_merger_consideration(slug: str, target: str) -> Optional[dict]:
    """Returns {"type": "cash"|"stock"|"mixed", "cash": float|None,
    "ratio": float|None, "quote": str} or None. Reads the signed
    merger agreement's own "you will receive ... per share" clause
    (naming the target, excluding hypothetical examples and
    equity-award payout formulas) straight from the filing's cached
    text -- the same deterministic, no-LLM convention as
    extract_shares_outstanding/extract_aggregate_value above. Meant as
    a fallback for a deal whose extracted Proposal rows never resolved
    a consideration_type ("unknown"), not a general override -- a
    caller should still prefer its own already-known price/type when
    one exists, and treat a value from here that CONFLICTS with an
    existing known price as a signal to leave it alone rather than
    silently pick a side (see bulk_stats._filing_consideration_fallback)."""
    text = _full_text(slug)
    if not text:
        return None
    candidates = [
        s
        for s in _sentences_mentioning(text, "receive")
        if _RECEIVE_RE.search(s) and _names_target(s, target) and not _HYPOTHETICAL_RE.search(s) and not _AWARD_RE.search(s)
    ]
    target_core = core_name(target)
    for s in candidates:
        cash_m = next(
            (m for m in _CASH_AMOUNT_RE.finditer(s) if "par value" not in s[max(0, m.start() - 15) : m.start()]), None
        )
        # A "for every N shares of [Target]'s OWN preferred stock, one
        # share of [Acquirer]" clause (a different share class's own
        # conversion ratio, e.g. a preferred stock, nested in the same
        # sentence as the real common-stock ratio) matches the same
        # "N shares of X" shape but names the TARGET right after the
        # number, not the acquirer (Verde Bio: the sentence's Series C
        # Preferred clause "for every 0.15 shares of Verde Series C
        # Preferred Stock, one share of..." would otherwise be picked
        # over the real (unnumbered in this OCR'd sentence) common
        # -stock ratio). Rejecting a match whose own "shares of ___"
        # clause names the target keeps only a ratio stated in terms
        # of the ACQUIRER's shares received per target share.
        ratio_m = next(
            (
                m
                for m in _RATIO_AMOUNT_RE.finditer(s)
                if "par value" not in s[max(0, m.start() - 15) : m.start()]
                and not (target_core and target_core in core_name(s[m.end() : m.end() + 60]))
            ),
            None,
        )
        if cash_m and ratio_m:
            return {
                "type": "mixed",
                "cash": float(cash_m.group(1).replace(",", "")),
                "ratio": float(ratio_m.group(1)),
                "quote": s.strip(),
            }
        if cash_m:
            return {"type": "cash", "cash": float(cash_m.group(1).replace(",", "")), "ratio": None, "quote": s.strip()}
        if ratio_m:
            return {"type": "stock", "cash": None, "ratio": float(ratio_m.group(1)), "quote": s.strip()}
    return None
