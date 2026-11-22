from datetime import date

from src.bulk_stats import compute_first_bidder_won_for_deal


def _proposal(proposer, day, status="open"):
    return {"date_resolved": date(2024, 1, day), "proposer": proposer, "status": status}


def _deal(target, acquirer, proposals):
    return {"target": target, "acquirer": acquirer, "proposals": proposals}


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


def test_no_non_target_proposal_excluded():
    d = _deal("Target Co", "Acquirer Co", [_proposal("Target Co", 1)])
    assert compute_first_bidder_won_for_deal(d) == (None, "no_non_target_proposal")
