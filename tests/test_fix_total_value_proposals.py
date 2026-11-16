from src.fix_total_value_proposals import _quotes_mention_aggregate_value, _is_implausible_per_share


def test_aggregate_value_without_per_share_is_flagged():
    # Werewolf Therapeutics/Ambros: every proposal is a "$X million"
    # valuation, with no per-share figure anywhere to compare against.
    assert _quotes_mention_aggregate_value(
        ["Werewolf's valuation would never fall below $5.5 million"]
    )
    assert _quotes_mention_aggregate_value(
        ["the final negotiated valuation for Werewolf would be $47.5 million"]
    )


def test_aggregate_value_with_per_share_is_not_flagged():
    # AVEO: the quote mentions BOTH the aggregate and the per-share
    # figure -- the extracted price corresponds to the per-share one,
    # and must not be treated as an aggregate value.
    assert not _quotes_mention_aggregate_value(
        ["an equity valuation of $500 million (or an implied $13.51 per share of AVEO common stock"]
    )


def test_hyphenated_per_share_is_recognized():
    # Cumberland/Apotex: "per-share" with a hyphen, not whitespace.
    assert not _quotes_mention_aggregate_value(
        ["the $100 million total transaction value implied a per-share value of approximately $6.68"]
    )


def test_per_share_with_words_in_between_is_recognized():
    # Aya/Cross Country: "per issued and outstanding share", not just
    # "per share".
    assert not _quotes_mention_aggregate_value(
        ["$608.6 million, which implied a value of approximately $18.00 per issued and outstanding share"]
    )


def test_billion_without_per_share_is_flagged():
    assert _quotes_mention_aggregate_value(
        ["an enterprise valuation of $12.5 billion, consideration of $5.8 billion of cash and $6.7 billion of shares"]
    )


def test_is_implausible_per_share_still_checks_ratio_and_absolute():
    assert _is_implausible_per_share(2000.0, 10.0, False)  # absolute
    assert _is_implausible_per_share(250.0, 10.0, False)  # 25x ratio
    assert not _is_implausible_per_share(12.0, 10.0, False)  # plausible
