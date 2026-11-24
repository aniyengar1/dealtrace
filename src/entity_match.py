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
from typing import Optional

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


# An optional single descriptive/role word ("Shareholder Party A",
# "Controlling Stockholder B") in front of the placeholder term itself
# -- still just an anonymization label, not a real company name,
# whichever role the filing happens to tag it with. shareholder/
# stockholder/equityholder can be either the role-adjective prefix
# ("Shareholder Party A") or the placeholder term itself
# ("Stockholder B"), so both lists include them.
#
# Deliberately an enumerated list, not a generic "any leading word"
# match: tried once, broke on "Real Acquirer Co" -- a real company
# name where "Co" (2 characters) coincidentally fits the trailing
# anonymization-letter-suffix shape just as well as "Party A" does, and
# "Acquirer" being in the core-word list let "Real" slide through as
# an unchecked adjective. The anchored suffix alone isn't a reliable
# enough signal; the adjective has to be a recognized one too.
_ANONYMIZED_PLACEHOLDER_RE = re.compile(
    r"^(the\s+)?(?:shareholder|stockholder|equityholder|controlling|significant|majority|"
    r"management|director|officer|founder)?\s*"
    r"(company|party|bidder|buyer|acquiror|acquirer|counterparty|sponsor|"
    r"shareholder|stockholder|equityholder)\s*[a-z0-9]{1,3}$",
    re.IGNORECASE,
)

# A reference to a company's own governance body, not a party at all --
# "Company Board", "EnLink Conflicts Committee", "the Special
# Committee", "Independent Directors" are how a filing's own text names
# the board/committee/directors negotiating on a company's behalf,
# never a real counterparty. Not anchored at the start, since the name
# in front ("EnLink", "Company") can be any company's own name, not
# just a fixed placeholder word -- matched at the end instead, requiring
# a word boundary (so "Chessboard" doesn't trip it just for containing
# "board") and an optional adjective ("Special", "Conflicts",
# "Independent", "Transaction", "Audit", "Compensation", "Governance")
# right before "Board"/"Committee" (with "Board" also accepting "of
# Directors"). Bare "Directors" is its own, separate alternative with a
# REQUIRED adjective -- "directors" alone is too generic a word to gate
# on safely the way "board"/"committee" can (nothing comparable to
# "Chessboard" risks colliding with "board", but plenty of real things
# could plausibly end in the word "directors"), so it only fires
# alongside one of the same qualifying adjectives ("Independent
# Directors", "Special Directors").
_GOVERNANCE_BODY_RE = re.compile(
    r"(?:^|\s)"
    r"(?:special|conflicts|independent|transaction|audit|compensation|governance)?\s*"
    r"(?:board(?:\s+of\s+directors)?|committee)$"
    r"|(?:^|\s)(?:special|conflicts|independent|transaction|audit|compensation|governance)\s+directors$",
    re.IGNORECASE,
)


def is_governance_body_reference(name: str) -> bool:
    """True for a reference to a company's own board/special/conflicts
    committee ("Company Board", "EnLink Conflicts Committee") -- never a
    real company, and (unlike an anonymized label such as "Party A")
    never a real bidder either: a target's own committee negotiating
    opposite a bidder isn't a second bidder."""
    if not name:
        return False
    return bool(_GOVERNANCE_BODY_RE.search(name.strip()))


def governance_body_subject(name: str) -> Optional[str]:
    """The company name referenced BY a governance-body phrase, if any --
    "SST VI" from "SST VI Special Committee", "AHL" from "AHL special
    committee", None from a bare "Conflicts Committee" with no company
    name attached at all. Not the same question as
    is_governance_body_reference (which only tests whether the SUFFIX
    looks like a board/committee); this extracts what comes before it,
    so a caller can check whether that subject is actually THIS deal's
    own target (an "acquirer" field that's really just the target's own
    committee referring to itself, not an independent second party) --
    see src.classify_deal_type._acquirer_is_target_governance_body."""
    if not name:
        return None
    n = name.strip()
    m = _GOVERNANCE_BODY_RE.search(n)
    if not m:
        return None
    subject = n[: m.start()].strip()
    # A leading bare article ("the Special Committee") is not a company
    # name -- same bare-term case as no subject at all.
    subject = re.sub(r"(?i)^the\b\s*", "", subject).strip()
    return subject or None


def is_anonymized_placeholder(name: str) -> bool:
    """True for a filing's own anonymization label ("Company A", "Party
    B", "Bidder 1") -- never a real company, so never a valid answer for
    "who is the acquirer" even when it's the most frequently mentioned
    name in a deal's proposals (see Global Blood Therapeutics / Pfizer,
    where "Company A" outnumbered "Pfizer" by raw mention count) -- or
    for a reference to the target's own board/special/conflicts
    committee (see is_governance_body_reference), which is just as
    unusable as an acquirer name as an anonymization label is (though,
    unlike a committee, an anonymized label like "Party A" IS a real
    bidder -- see is_governance_body_reference for that distinction)."""
    if not name:
        return False
    n = name.strip()
    return bool(_ANONYMIZED_PLACEHOLDER_RE.match(n) or is_governance_body_reference(n))


# A numbered-fund/series-sibling convention this dataset's filings use
# repeatedly (Golub Capital BDC 3, FS KKR Capital Corp. II) sometimes
# keeps the LAST word of a company's name as a unit in its own short
# form, rather than reducing it to one letter the way every other word
# is reduced -- "SST VI" for "Strategic Storage Trust VI" keeps "VI"
# whole (not "V"), "SSGT III" for its own "...Growth Trust III" sibling
# keeps "III" whole. Deliberately narrow: only the LAST word, only up
# to 4 characters (so this can't absorb an ordinary multi-letter word
# and turn an unrelated short string into a false match), and the short
# form's own internal whitespace is stripped before comparing (a filing
# sometimes writes a numbered short form with a space, "SST VI", where
# a bare initials-style acronym never would).
def _is_initials_plus_kept_suffix(short: str, long_name: str) -> bool:
    words = core_name(long_name).split()
    if len(words) < 2:
        return False
    last = words[-1]
    if not last.isalpha() or not (1 <= len(last) <= 4):
        return False
    candidate = "".join(w[0] for w in words[:-1]).upper() + last.upper()
    return short.upper() == candidate


def is_acronym_of(short: str, long_name: str) -> bool:
    """True if `short` looks like an initials/acronym abbreviation of
    `long_name` -- "USS" for "UNITED STATES STEEL CORP". Requires the
    long name to have at least 2 significant words (so a single-word
    name can't trivially "match" any one-letter string) and the
    candidate acronym to look like one (letters only, 2-6 characters) --
    guards against an unrelated short name coincidentally matching."""
    s = short.strip()
    s_nospace = s.replace(" ", "")
    if not s_nospace or not s_nospace.isalpha() or not (2 <= len(s_nospace) <= 6):
        return False
    words = core_name(long_name).split()
    if len(words) < 2:
        return False
    if s_nospace.upper() in (initials(long_name), _initials_including_suffix(long_name)):
        return True
    return _is_initials_plus_kept_suffix(s_nospace, long_name)


# Words real stock tickers conventionally drop when abbreviating a
# company name to 3-5 letters ("Western Asset Mortgage Capital Corp" ->
# NYSE: WMC, dropping "Asset") -- not an exhaustive list, just the
# common filler words this pipeline has seen cause a real ticker to
# diverge from a plain one-letter-per-word initialism.
_TICKER_FILLER_WORDS = {
    "asset", "assets", "capital", "holding", "holdings", "investment",
    "investments", "management", "trust", "realty", "group", "fund",
}


def _is_ticker_of(short: str, long_name: str) -> bool:
    """True if `short` plausibly IS `long_name`'s own stock ticker or
    informal short name, rather than a different company's -- broader
    than is_acronym_of in two ways real tickers diverge from a strict
    one-letter-per-word initialism: (1) dropping a filler word
    (_TICKER_FILLER_WORDS) before taking initials ("WMC" only works for
    "Western Asset Mortgage Capital" once "Asset" is dropped); (2)
    being a literal prefix of the long name's own squished-together
    letters ("USAR" is literally the first four letters of
    "usarareearth", the squished form of "USA Rare Earth" -- a company
    whose own ticker keeps "USA" as a unit rather than reducing it to
    one letter, a convention no fixed initials formula predicts).
    Exists specifically to stop an acquirer-resolution candidate from
    turning out to just be the target's own ticker (deal_metrics must
    never show a deal's acquirer as the target itself)."""
    s = short.strip()
    if not s or not s.isalpha() or not (2 <= len(s) <= 6):
        return False
    words = core_name(long_name).split()
    if len(words) >= 2:
        # Try dropping each filler word ONE AT A TIME, not all of them
        # at once -- "Western Asset Mortgage Capital" drops only
        # "Asset" (WMC keeps the initial for "Capital"); dropping every
        # filler word simultaneously would wrongly give "WM".
        filler_positions = [i for i, w in enumerate(words) if w in _TICKER_FILLER_WORDS]
        candidates = [words] + [[w for j, w in enumerate(words) if j != i] for i in filler_positions]
        for candidate_words in candidates:
            if len(candidate_words) < 2:
                continue
            if s.upper() == "".join(w[0] for w in candidate_words).upper():
                return True
    squished = re.sub(r"[^a-z]", "", core_name(long_name))
    return len(s) >= 3 and squished.startswith(s.lower())
