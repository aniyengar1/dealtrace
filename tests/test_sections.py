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
