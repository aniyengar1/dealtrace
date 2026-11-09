import json
from pathlib import Path

import pytest

import src.sections as sections_module
from src.sections import (
    OPINION_SUBSECTION_RE,
    SECTION_WORD_WARNING_THRESHOLD,
    _strip_page_reference,
    extract_sections,
    run,
    save_sections,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mini_filing.html"
NO_MARKUP_FIXTURE = Path(__file__).parent / "fixtures" / "mini_filing_no_markup.html"


def test_finds_background_of_the_merger():
    sections = extract_sections(FIXTURE.read_text())
    assert "background_of_the_merger" in sections
    texts = [p["text"] for p in sections["background_of_the_merger"]["paragraphs"]]
    assert any("non-binding indication of interest" in t for t in texts)


def test_background_excludes_next_section():
    sections = extract_sections(FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["background_of_the_merger"]["paragraphs"])
    assert "recommends that stockholders" not in texts


def test_finds_opinion_section_with_same_level_subsection():
    sections = extract_sections(FIXTURE.read_text())
    key = "opinion_of_example_advisor_llc"
    assert key in sections
    texts = [p["text"] for p in sections[key]["paragraphs"]]
    # The DCF subsection is at the same heading depth as "Opinion of ..." --
    # it must still be included, not treated as a section-ending sibling.
    assert any("discount rate range" in t for t in texts)


def test_opinion_section_excludes_unrelated_trailing_section():
    sections = extract_sections(FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "should not be included" not in texts


def test_opinion_section_stops_at_a_same_level_non_opinion_sibling():
    # Regression guard for the Zendesk over-capture bug: a same-level
    # heading that is neither a recognized methodology subsection
    # ("... Analysis", "Miscellaneous", "General") nor another advisor's
    # "Opinion of ..." must still end the section -- it must not be
    # treated as "not an opinion heading, so keep going" (that's what let
    # "Interests of Zendesk's Executive Officers ... in the Merger" pull
    # in several unrelated chapters after the real Goldman Sachs opinion).
    sections = extract_sections(FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "same-level non-opinion sibling" not in texts


def test_toc_duplicate_heading_is_not_mistaken_for_the_section():
    sections = extract_sections(FIXTURE.read_text())
    # The TOC lists "Background of the Merger" with no body text after it;
    # the real section (with actual prose) must be the one returned.
    assert sections["background_of_the_merger"]["word_count"] > 0
    assert len(sections["background_of_the_merger"]["paragraphs"]) == 2


def test_table_becomes_one_paragraph_with_pipe_separated_rows():
    sections = extract_sections(FIXTURE.read_text())
    texts = [p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"]]
    table_texts = [t for t in texts if "|" in t]
    assert len(table_texts) == 1
    assert table_texts[0] == "Method | Implied Price\nDCF | $95.00-$115.00"


def test_table_gutter_spacer_cells_are_dropped():
    sections = extract_sections(FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    # The gutter <td>s carry only a zero-width space for visual spacing --
    # they must not show up as empty " | " segments in the rendered row.
    assert " |  | " not in texts


@pytest.mark.parametrize(
    "heading",
    [
        "Discounted Cash Flow Analysis",
        "Selected Companies Analysis",
        "Selected Transactions Analysis",
        "Illustrative Discounted Cash Flow Analysis",
        "Summary of Financial Analyses",
        "Precedent Transactions Multiples Analysis",
        "Other Information",
        "Miscellaneous",
        "General",
    ],
)
def test_opinion_subsection_re_matches_known_methodology_headings(heading):
    assert OPINION_SUBSECTION_RE.match(heading)


@pytest.mark.parametrize(
    "heading",
    [
        "Interests of Zendesk's Executive Officers and Directors in the Merger",
        "Restrictions on Solicitation of Alternative Proposals",
        "Opinion of Morgan Stanley & Co. LLC",
    ],
)
def test_opinion_subsection_re_does_not_match_true_siblings(heading):
    assert not OPINION_SUBSECTION_RE.match(heading)


def test_save_sections_warns_when_a_section_is_implausibly_large(tmp_path, capsys):
    oversized = {
        "key": {
            "section_key": "key",
            "heading_text": "Big Section",
            "heading_paragraph_id": "p1",
            "word_count": SECTION_WORD_WARNING_THRESHOLD + 1,
            "paragraphs": [],
        }
    }
    save_sections(oversized, tmp_path)
    captured = capsys.readouterr()
    assert "WARNING" in captured.out


def test_save_sections_does_not_warn_for_a_normal_sized_section(tmp_path, capsys):
    normal = {
        "key": {
            "section_key": "key",
            "heading_text": "Normal Section",
            "heading_paragraph_id": "p1",
            "word_count": 1000,
            "paragraphs": [],
        }
    }
    save_sections(normal, tmp_path)
    captured = capsys.readouterr()
    assert "WARNING" not in captured.out


def test_extra_continue_headings_overrides_a_same_level_sibling():
    # "Interests of Certain Persons in the Merger" is the fixture's true
    # sibling (see test_opinion_section_stops_at_a_same_level_non_opinion_
    # sibling) -- the per-deal override must be able to treat it as a
    # continuation instead, for the rare case where a filing's own HTML
    # mistags a real subsection at the sibling's depth.
    sections = extract_sections(
        FIXTURE.read_text(),
        extra_continue_headings=["Interests of Certain Persons in the Merger"],
    )
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "same-level non-opinion sibling" in texts
    # The true shallower sibling ("Certain Other Matters") must still end
    # the section even with the override in place.
    assert "This paragraph should not be included" not in texts


def test_extra_continue_headings_defaults_to_none_without_changing_behavior():
    sections = extract_sections(FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "same-level non-opinion sibling" not in texts


def test_run_namespaces_sections_under_the_deal_slug(tmp_path, monkeypatch):
    import src.sections as sections_module

    monkeypatch.setattr(sections_module, "DATA_SECTIONS", tmp_path)
    html_path = tmp_path / "filing.html"
    html_path.write_text(FIXTURE.read_text())

    run(html_path, "example_deal")

    assert (tmp_path / "example_deal" / "background_of_the_merger.json").exists()
    assert not (tmp_path / "background_of_the_merger.json").exists()


def test_run_passes_through_extra_continue_headings(tmp_path, monkeypatch):
    import src.sections as sections_module

    monkeypatch.setattr(sections_module, "DATA_SECTIONS", tmp_path)
    html_path = tmp_path / "filing.html"
    html_path.write_text(FIXTURE.read_text())

    run(html_path, "example_deal", ["Interests of Certain Persons in the Merger"])

    opinion = json.loads((tmp_path / "example_deal" / "opinion_of_example_advisor_llc.json").read_text())
    texts = " ".join(p["text"] for p in opinion["paragraphs"])
    assert "same-level non-opinion sibling" in texts


# Regression guard for the fallback (markup-less) parser added for filings
# with no semantic h1-h5 headings: Splunk's, Zendesk's, and Cvent's
# filings all DO have real heading markup, so they must never take that
# code path, and their sections must come out exactly as they did before
# the fallback parser existed. Skipped (not failed) when the cached raw
# HTML isn't present locally, since data/raw/ is gitignored -- this is a
# development-environment regression check, not a portable one.
RAW_DIR = Path(__file__).parent.parent / "data" / "raw"

KNOWN_GOOD_DEALS = {
    "splunk_inc_defm14a.html": {
        "background_of_the_merger": (7043, 67, "Background of the Merger"),
        "management_projections": (1967, 14, "Management Projections"),
        "opinion_of_morgan_stanley_co_llc": (5805, 75, "Opinion of Morgan Stanley & Co. LLC"),
        "opinion_of_qatalyst_partners_lp": (5209, 49, "Opinion of Qatalyst Partners LP"),
    },
    "zendesk,_inc_defm14a.html": {
        "background_of_the_merger": (9537, 96, "Background of the Merger"),
        "management_projections": (2397, 28, "Certain Financial Projections"),
        "opinion_of_goldman_sachs_co_llc": (6610, 81, "Opinion of Goldman Sachs & Co. LLC"),
        "opinion_of_qatalyst_partners_lp": (4124, 40, "Opinion of Qatalyst Partners LP"),
    },
    "cvent_holding_corp_defm14a.html": {
        "background_of_the_merger": (13952, 131, "Background of the Merger"),
        "management_projections": (2127, 22, "Certain Financial Projections"),
        "opinion_of_j_p_morgan": (4235, 54, "Opinion of J.P. Morgan"),
        "opinion_of_qatalyst_partners": (4502, 41, "Opinion of Qatalyst Partners"),
    },
}

ZENDESK_OVERRIDES = ["EV/NTM Revenue Multiple Over Time"]


@pytest.mark.parametrize("html_filename", list(KNOWN_GOOD_DEALS))
def test_known_good_deals_unaffected_by_fallback_parser(html_filename):
    html_path = RAW_DIR / html_filename
    if not html_path.exists():
        pytest.skip(f"{html_path} not cached locally (data/raw/ is gitignored)")

    overrides = ZENDESK_OVERRIDES if html_filename.startswith("zendesk") else None
    sections = extract_sections(html_path.read_text(encoding="utf-8", errors="replace"), overrides)

    expected = KNOWN_GOOD_DEALS[html_filename]
    assert set(sections) == set(expected), (set(sections), set(expected))
    for key, (word_count, n_paragraphs, heading_text) in expected.items():
        section = sections[key]
        assert section["word_count"] == word_count, key
        assert len(section["paragraphs"]) == n_paragraphs, key
        assert section["heading_text"] == heading_text, key


# --- Fallback parser (no semantic heading markup) ---------------------------


@pytest.fixture(autouse=False)
def low_fallback_prose_threshold(monkeypatch):
    # The no-markup fixture is tiny for readability; real filings clear
    # the real ~300-word minimum easily, but this fixture's "background"
    # body is only a few short sentences, so the threshold needs lowering
    # for it to be recognized as the real section rather than a TOC entry.
    monkeypatch.setattr(sections_module, "_FALLBACK_MIN_PROSE_WORDS", 10)


def test_extract_sections_dispatches_to_fallback_when_no_headings_found(low_fallback_prose_threshold):
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    assert "background_of_the_merger" in sections
    assert "opinion_of_example_advisor_llc" in sections


def test_fallback_skips_the_table_of_contents(low_fallback_prose_threshold):
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    # The TOC's "Background of the Merger" link has ~0 words before the
    # next candidate; the real (bold) heading must be the one selected.
    assert sections["background_of_the_merger"]["heading_paragraph_id"] != "p00002"
    texts = " ".join(p["text"] for p in sections["background_of_the_merger"]["paragraphs"])
    assert "non-binding indication of interest" in texts


def test_fallback_background_excludes_quoted_letter_noise_as_a_stop_signal(low_fallback_prose_threshold):
    # "Dear Marty and Alan:" / "Sincerely," / "/s/ Jane Doe" are short and
    # bold-or-not, but none of them name a known standard chapter, so they
    # must not end the section early -- only the real
    # "Recommendation of..." heading should.
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["background_of_the_merger"]["paragraphs"])
    assert "continued negotiating the terms" in texts


def test_fallback_background_stops_at_known_standard_heading(low_fallback_prose_threshold):
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["background_of_the_merger"]["paragraphs"])
    assert "recommends that stockholders" not in texts


def test_fallback_opinion_section_includes_same_level_methodology_subsection(low_fallback_prose_threshold):
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "discount rate range" in texts


def test_fallback_opinion_section_stops_at_true_sibling(low_fallback_prose_threshold):
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    texts = " ".join(p["text"] for p in sections["opinion_of_example_advisor_llc"]["paragraphs"])
    assert "should not be included" not in texts


def test_strip_page_reference_removes_trailing_page_annotation():
    assert _strip_page_reference("Opinion of Qatalyst Partners (page 41)") == "Opinion of Qatalyst Partners"
    assert _strip_page_reference("Opinion of X (page 52 )") == "Opinion of X"


def test_strip_page_reference_leaves_plain_headings_untouched():
    assert _strip_page_reference("Opinion of Qatalyst Partners") == "Opinion of Qatalyst Partners"


def test_fallback_collapses_page_reference_variant_onto_the_real_opinion_heading(low_fallback_prose_threshold):
    # The fixture's TOC entry is "Opinion of Example Advisor LLC (page 41)"
    # -- without stripping the page reference this would be tracked as a
    # second, separate advisor rather than the same one as the real heading.
    sections = extract_sections(NO_MARKUP_FIXTURE.read_text())
    opinion_keys = [k for k in sections if k.startswith("opinion_of")]
    assert opinion_keys == ["opinion_of_example_advisor_llc"]
