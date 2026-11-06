from pathlib import Path

from src.sections import extract_sections

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
