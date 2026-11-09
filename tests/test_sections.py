import json
from pathlib import Path

import pytest

from src.sections import (
    OPINION_SUBSECTION_RE,
    SECTION_WORD_WARNING_THRESHOLD,
    extract_sections,
    run,
    save_sections,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mini_filing.html"


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
