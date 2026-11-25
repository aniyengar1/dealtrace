from datetime import date
from unittest.mock import patch

from src.bulk_stats import (
    _effective_final,
    _final_entry,
    compute_first_bidder_won_for_deal,
    compute_pct_bump_for_deal,
    stat_first_bidder_is_acquirer,
)


def _proposal(
    proposer, day, status="open", price_low=None, price_high=None, consideration_type="cash", source_quotes=None
):
    return {
        "date_resolved": date(2024, 1, day),
        "proposer": proposer,
        "status": status,
        "price_low": price_low,
        "price_high": price_high,
        "consideration_type": consideration_type,
        "source_quotes": source_quotes or [],
    }


def _deal(target, acquirer, proposals, slug="fake_slug"):
    return {"target": target, "acquirer": acquirer, "proposals": proposals, "slug": slug}


def test_target_counter_offer_never_credited_as_the_winner():
    # Real shape: bulk_1166388_000119312525243585 (Verint/Thoma Bravo) --
    # the latest/accepted entry is literally the TARGET's own
    # willingness-to-accept, not Thoma Bravo's.
    d = _deal(
        "Verint",
        "Thoma Bravo",
        [
            _proposal("Thoma Bravo", 1),
            _proposal("Verint", 2, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_fuzzy_match_same_bidder_different_name_string():
    # Real shape: bulk_1837686_000110465925101569 (Vimeo) -- "Bending
    # Spoons group" and "Bending Spoons US" are the same real bidder.
    d = _deal(
        "Vimeo",
        "Bending Spoons US",
        [
            _proposal("Bending Spoons group", 1),
            _proposal("Bending Spoons US", 2, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_shell_term_aliases_collapse_to_the_same_bidder():
    # Real shape: bulk_1334978_000121390026042721 (Clear Channel
    # Outdoor) -- "Consortium" first, then its own newly formed
    # "Merger Sub" at signing; both are the SAME real party.
    d = _deal(
        "Clear Channel Outdoor Holdings, Inc.",
        "Consortium",
        [
            _proposal("Consortium", 1),
            _proposal("Merger Sub", 2, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_genuinely_different_later_bidder_still_counts_as_a_loss():
    d = _deal(
        "Target Co",
        "Second Bidder",
        [
            _proposal("First Bidder", 1),
            _proposal("Second Bidder", 2, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (False, None)


def test_targets_own_committee_never_credited_as_a_second_bidder():
    # Real shape: bulk_1592000_000121390024113605 (EnLink/ONEOK) -- the
    # accepted entry is the EnLink Conflicts Committee's own
    # confirmation of ONEOK's price, not a second bidder's winning bid.
    d = _deal(
        "EnLink Midstream, LLC",
        "ONEOK",
        [
            _proposal("ONEOK", 1),
            _proposal("EnLink Conflicts Committee", 2, status="rejected"),
            _proposal("ONEOK", 3),
            _proposal("EnLink Conflicts Committee", 4, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_partial_minority_stake_proposal_is_not_a_bidder():
    # Real shape: bulk_1847590_000114036126038492 (Bowman Consulting /
    # Bernhard) -- "Party D"'s offer was for a minority interest in the
    # combined enterprise, not an acquisition of the whole target, so
    # it isn't a rival bid at all; Bernhard is the only real bidder.
    d = _deal(
        "Bowman Consulting Group Ltd.",
        "Bernhard",
        [
            _proposal(
                "Party D",
                1,
                status="withdrawn",
            ),
            _proposal("Bernhard", 2, status="accepted"),
        ],
    )
    d["proposals"][0]["source_quotes"] = [
        "a potential business combination transaction in which the Company Stockholders would own, collectively, a minority interest in the combined enterprise."
    ]
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_committee_exempted_when_it_is_itself_the_stored_acquirer():
    # If the acquirer field itself ended up a committee name, excluding
    # every committee-named proposer would wrongly drop the real
    # winning bidder entirely -- same edge case n_bidders already
    # guards against via its own eventual-acquirer exemption.
    d = _deal(
        "Target Co",
        "Acquirer Special Committee",
        [
            _proposal("Acquirer Special Committee", 1),
            _proposal("Acquirer Special Committee", 2, status="accepted"),
        ],
    )
    assert compute_first_bidder_won_for_deal(d) == (True, None)


def test_no_non_target_proposal_excluded():
    d = _deal("Target Co", "Acquirer Co", [_proposal("Target Co", 1)])
    assert compute_first_bidder_won_for_deal(d) == (None, "no_non_target_proposal")


def test_contested_stat_excludes_one_bidder_deals():
    # A 1-bidder deal wins by definition (there's no one else it could
    # have lost to) -- contested_only must drop it from both the
    # numerator and denominator, not just the numerator.
    one_bidder_deal = _deal("Target Co", "Only Bidder", [_proposal("Only Bidder", 1, status="accepted")])
    two_bidder_deal = _deal(
        "Target Co",
        "Second Bidder",
        [_proposal("First Bidder", 1), _proposal("Second Bidder", 2, status="accepted")],
    )
    all_stat = stat_first_bidder_is_acquirer([one_bidder_deal, two_bidder_deal])
    contested_stat = stat_first_bidder_is_acquirer([one_bidder_deal, two_bidder_deal], contested_only=True)
    assert all_stat["n"] == 2
    assert contested_stat["n"] == 1
    assert contested_stat["pct_first_bidder_is_eventual_acquirer"] == 0.0
    assert "CONTESTED" in contested_stat["definition"]


def test_final_entry_prefers_open_over_later_dated_rejection():
    # Real shape: Vista Outdoor -- MNC's own unsolicited, never-accepted
    # $37.50 bid is dated after the real signed terms in deals where a
    # rival's rejected/withdrawn counter happens to be the latest *dated*
    # proposal. The latest *standing* (open) proposal is the better pick
    # than a later-dated proposal nobody acted on.
    dated = [
        _proposal("Acquirer", 1, status="open", price_low=32.0),
        _proposal("Rival", 2, status="withdrawn", price_low=37.5),
    ]
    assert _final_entry(dated)["proposer"] == "Acquirer"


def test_final_entry_prefers_accepted_over_open():
    dated = [
        _proposal("Acquirer", 1, status="accepted", price_low=30.0),
        _proposal("Rival", 2, status="open", price_low=35.0),
    ]
    assert _final_entry(dated)["proposer"] == "Acquirer"


def test_final_entry_falls_back_to_latest_when_nothing_is_open_or_accepted():
    # A deal that fell through entirely has no open/accepted proposal at
    # all -- there's no better candidate than the latest-dated one.
    dated = [
        _proposal("Bidder", 1, status="withdrawn", price_low=20.0),
        _proposal("Bidder", 2, status="rejected", price_low=22.0),
    ]
    assert _final_entry(dated)["price_low"] == 22.0


def test_pct_bump_excludes_cash_plus_cvr_deal():
    # Real shape: Theseus Pharmaceuticals -- "$3.94 in cash ... plus one
    # contingent value right (CVR)" per share. The stored price is only
    # the base-cash leg, so a % bump computed from it alone would
    # misrepresent the real (contingent, unknown-at-signing) consideration.
    d = _deal(
        "Target Co",
        "Parent",
        [
            _proposal("Parent", 1, status="superseded", price_low=3.0, price_high=3.0),
            _proposal(
                "Target Co",
                2,
                status="accepted",
                price_low=3.94,
                price_high=3.94,
                source_quotes=["$3.94 in cash per share plus one contingent value right (CVR)"],
            ),
        ],
    )
    assert compute_pct_bump_for_deal(d) == (None, "cash_plus_cvr")


def test_effective_final_fills_in_type_from_filing_fallback_when_price_already_agrees():
    # Real shape: Activision Blizzard -- the stored proposal already
    # has the right price ($95.00) but an unresolved "unknown" type;
    # the filing fallback should only need to supply the type.
    d = _deal(
        "Activision Blizzard",
        "Microsoft",
        [_proposal("Microsoft", 1, status="accepted", price_low=95.0, consideration_type="unknown")],
    )
    with patch(
        "src.bulk_stats.extract_merger_consideration",
        return_value={"type": "cash", "cash": 95.0, "ratio": None, "quote": "receive $95.00 in cash"},
    ):
        final = _effective_final(d)
    assert final["consideration_type"] == "cash"
    assert final["price_low"] == 95.0


def test_effective_final_leaves_unknown_when_filing_fallback_conflicts_with_stored_price():
    # Real shape: ChemoCentryx -- the filing's own Q&A says $52.00, but
    # the stored proposal is a stale $44.00 negotiating round. A
    # disagreement is a sign the stored data needs human review, not
    # something to silently overrule from here.
    d = _deal(
        "ChemoCentryx",
        "Amgen",
        [_proposal("Amgen", 1, status="accepted", price_low=44.0, consideration_type="unknown")],
    )
    with patch(
        "src.bulk_stats.extract_merger_consideration",
        return_value={"type": "cash", "cash": 52.0, "ratio": None, "quote": "receive $52.00 in cash"},
    ):
        final = _effective_final(d)
    assert final["consideration_type"] == "unknown"
    assert final["price_low"] == 44.0


def test_effective_final_backfills_missing_price_from_filing_fallback():
    # Real shape: Verde Bio/SSTC -- the only extracted Proposal is a
    # vague "entered into a letter of intent" with no price at all, but
    # the filing itself states a fixed exchange ratio.
    d = _deal(
        "Verde",
        "SSTC",
        [_proposal("Verde", 1, status="accepted", price_low=None, price_high=None, consideration_type="unknown")],
    )
    with patch(
        "src.bulk_stats.extract_merger_consideration",
        return_value={"type": "stock", "cash": None, "ratio": 300.0, "quote": "one share of SSTC for every 300 shares"},
    ):
        final = _effective_final(d)
    assert final["consideration_type"] == "stock"
    assert final["price_low"] == 300.0
    assert final["price_high"] == 300.0


def test_effective_final_returns_plain_final_when_no_fallback_match():
    d = _deal(
        "Target Co",
        "Acquirer Co",
        [_proposal("Acquirer Co", 1, status="accepted", price_low=10.0, consideration_type="unknown")],
    )
    with patch("src.bulk_stats.extract_merger_consideration", return_value=None):
        final = _effective_final(d)
    assert final["consideration_type"] == "unknown"
    assert final["price_low"] == 10.0
