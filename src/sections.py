"""Parse a DEFM14A HTML filing into paragraphs and locate key sections.

SEC filing HTML (as produced by financial printers) lays out paragraphs as
leaf <div>/<p> elements rather than semantic headings. Heading paragraphs are
distinguished by a CSS class of the form h1..h5 indicating outline depth;
everything else is body text. Table-of-contents entries repeat the same
heading text but carry a body-text class (not an h-class), which is how we
tell a real section heading apart from its TOC listing.

Section boundaries are found by scanning forward from a heading until the
next heading of equal-or-shallower depth. Some headings (e.g. "Opinion of
Qatalyst Partners LP") appear twice -- once in a short Summary chapter and
once in the detailed body chapter -- so we keep the occurrence with the most
content.
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

DATA_SECTIONS = Path(__file__).resolve().parent.parent / "data" / "sections"

_HEADING_CLASS_RE = re.compile(r"^h([1-5])$")
_TOC_MARKER_RE = re.compile(r"^(TABLE OF CONTENTS\s*)+", re.IGNORECASE)
_PAGE_NUMBER_RE = re.compile(r"^[\d\s\-–—]*$")

SECTION_SPECS = {
    "background_of_the_merger": [r"^Background of the Merger$"],
    "management_projections": [
        r"^Certain Unaudited Prospective Financial Information$",
        r"^Unaudited Prospective Financial Information$",
        r"^Management Projections$",
        r"^Certain Financial Projections$",
    ],
}
OPINION_HEADING_RE = re.compile(r"^Opinion of (?!.*\band\b).+$")

# Valuation-methodology subheadings ("Discounted Cash Flow Analysis",
# "Summary of Financial Analyses", "Other Information", a closing
# "Miscellaneous"/"General" fee disclosure) render at the SAME heading
# depth as "Opinion of X" in some filings' flat heading hierarchy -- the
# HTML carries no distinguishing style/class between a true subsection and
# a true sibling chapter, only the text says which one it is. These
# continue the opinion section instead of ending it; any OTHER same-level
# heading ends it, including ones that aren't "Opinion of <other
# advisor>" either (that was the over-capture bug: a non-opinion sibling
# like "Interests of Zendesk's Executive Officers ... in the Merger" was
# wrongly treated as still part of the opinion, pulling in everything up
# to the next *shallower* heading -- several chapters later).
#
# This is a heuristic over real-world filing text, not a closed set: a
# same-level subheading whose text matches none of these (and isn't
# caught by a deeper heading level either) will still end the section
# early. Splunk's and Zendesk's filings needed exactly this list; a new
# filing may need another phrase added here if its real opinion section
# ends up suspiciously short.
OPINION_SUBSECTION_RE = re.compile(
    r".*\bAnalys(is|es)$|^Miscellaneous$|^General$|^Other Information$", re.IGNORECASE
)

# A real DEFM14A section this pipeline looks for is at most a few thousand
# words; anything much bigger is a sign the end-boundary logic walked past
# the section's real end into unrelated chapters.
SECTION_WORD_WARNING_THRESHOLD = 8000


class Paragraph:
    __slots__ = ("id", "text", "level")

    def __init__(self, para_id: str, text: str, level: int | None):
        self.id = para_id
        self.text = text
        self.level = level

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text}


_ZERO_WIDTH_RE = re.compile(r"[​ ]")


def _table_text(table_tag) -> str:
    """Render a <table> as "cell | cell" rows, one row per line.

    Financial-printer HTML pads tables with empty "gutter" <td>s (often just
    a zero-width space) purely for visual column spacing; those carry no
    content, so they're dropped rather than appearing as empty cells.
    """
    lines = []
    for row in table_tag.find_all("tr"):
        cells = []
        for cell in row.find_all(["td", "th"]):
            text = cell.get_text(" ", strip=True)
            text = _ZERO_WIDTH_RE.sub("", text).strip()
            if text:
                cells.append(text)
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def parse_paragraphs(html: str) -> list[Paragraph]:
    """Extract an ordered list of leaf-level paragraphs with stable IDs.

    A paragraph is a <div> or <p> with no nested div/p/table (i.e. its text
    is a single flowing block). Heading paragraphs carry a level (1-5) taken
    from an h1..h5 CSS class; body paragraphs have level=None.

    A <table> is its own paragraph instead: its rows/cells have no flowing
    prose structure, so splitting it into leaf divs (one per cell) would
    scatter a single row across unrelated paragraph IDs. Elements nested
    inside a table are skipped in the main loop since the table's own entry
    already covers their text.
    """
    soup = BeautifulSoup(html, "lxml")

    paragraphs: list[Paragraph] = []
    counter = 0
    for tag in soup.find_all(["div", "p", "table"]):
        if tag.name == "table":
            if tag.find_parent("table") is not None:
                continue  # nested table -- captured as text by the outer one
            text = _table_text(tag)
            if not text:
                continue
            counter += 1
            paragraphs.append(Paragraph(f"p{counter:05d}", text, None))
            continue

        if tag.find_parent("table") is not None:
            continue  # already captured by the table's own paragraph
        if tag.find(["div", "p", "table"]):
            continue  # not a leaf -- its text is captured by its children

        text = tag.get_text(" ", strip=True)
        text = _TOC_MARKER_RE.sub("", text).strip()
        if not text or _PAGE_NUMBER_RE.match(text):
            continue

        level = None
        for cls in tag.get("class") or []:
            m = _HEADING_CLASS_RE.match(cls)
            if m:
                level = int(m.group(1))

        counter += 1
        paragraphs.append(Paragraph(f"p{counter:05d}", text, level))

    return paragraphs


def _section_span(
    paragraphs: list[Paragraph], start_idx: int, continue_re: "re.Pattern | None" = None
) -> tuple[int, int]:
    """Return (word_count, end_idx) for the body content following a heading.

    A heading strictly shallower than the start heading always ends the
    section. A heading at the *same* level ends it too, UNLESS `continue_re`
    is given and matches that heading's text -- this lets callers treat
    recognized same-level subheadings (e.g. "Discounted Cash Flow Analysis"
    nested under "Opinion of X" at the same h3 depth) as part of the
    section instead of a sibling that should end it. Any other same-level
    heading ends the section even if it doesn't look like "the next
    sibling chapter" either -- there is no third option.
    """
    level = paragraphs[start_idx].level
    word_count = 0
    j = start_idx + 1
    while j < len(paragraphs):
        p = paragraphs[j]
        if p.level is not None:
            if p.level < level:
                break
            if p.level == level and not (continue_re and continue_re.match(p.text)):
                break
        word_count += len(p.text.split())
        j += 1
    return word_count, j


def _best_match(
    paragraphs: list[Paragraph], patterns: list[str], continue_re: "re.Pattern | None" = None
) -> tuple[int, int, int] | None:
    """Find the best-scoring (most content) heading occurrence matching any pattern.

    Returns (start_idx, end_idx, word_count) or None if no heading matches.
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    best = None
    for i, para in enumerate(paragraphs):
        if para.level is None:
            continue
        if not any(c.match(para.text) for c in compiled):
            continue
        word_count, end_idx = _section_span(paragraphs, i, continue_re)
        if best is None or word_count > best[2]:
            best = (i, end_idx, word_count)
    return best


def find_opinion_headings(paragraphs: list[Paragraph]) -> list[str]:
    """Return the distinct per-advisor opinion heading texts found in the doc."""
    seen = []
    for para in paragraphs:
        if para.level is not None and OPINION_HEADING_RE.match(para.text):
            if para.text not in seen:
                seen.append(para.text)
    return seen


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug


def extract_sections(html: str, extra_continue_headings: list[str] | None = None) -> dict[str, dict]:
    """Locate target sections and return {section_key: section_dict}.

    `extra_continue_headings`, if given, is a per-deal override: exact
    heading texts that should continue an opinion section instead of
    ending it, on top of the general OPINION_SUBSECTION_RE patterns. This
    exists for one-off filing quirks a general pattern can't anticipate
    -- e.g. a sub-subsection mistagged at the same heading depth as
    "Opinion of X" instead of one level deeper like its siblings (see
    run.py's DEALS["zendesk"]["section_boundary_overrides"] for the real
    case this was added for). Prefer extending OPINION_SUBSECTION_RE
    itself when the heading text is a genuinely common pattern across
    filings; use this when it's a single filing's own inconsistency.
    """
    paragraphs = parse_paragraphs(html)

    sections: dict[str, dict] = {}

    for key, patterns in SECTION_SPECS.items():
        match = _best_match(paragraphs, patterns)
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        sections[key] = {
            "section_key": key,
            "heading_text": heading_para.text,
            "heading_paragraph_id": heading_para.id,
            "word_count": word_count,
            "paragraphs": [p.to_dict() for p in body],
        }

    continue_re = OPINION_SUBSECTION_RE
    if extra_continue_headings:
        extra_pattern = "|".join(f"^{re.escape(h)}$" for h in extra_continue_headings)
        continue_re = re.compile(
            f"{OPINION_SUBSECTION_RE.pattern}|{extra_pattern}", re.IGNORECASE
        )

    for heading_text in find_opinion_headings(paragraphs):
        match = _best_match(paragraphs, [re.escape(heading_text)], continue_re=continue_re)
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        key = f"opinion_of_{_slugify(heading_text.replace('Opinion of', ''))}"
        sections[key] = {
            "section_key": key,
            "heading_text": heading_para.text,
            "heading_paragraph_id": heading_para.id,
            "word_count": word_count,
            "paragraphs": [p.to_dict() for p in body],
        }

    return sections


def save_sections(sections: dict[str, dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for key, section in sections.items():
        path = out_dir / f"{key}.json"
        path.write_text(json.dumps(section, indent=2))
        paths.append(path)
        print(f"{key}: {section['word_count']} words, {len(section['paragraphs'])} paragraphs -> {path}")
        if section["word_count"] > SECTION_WORD_WARNING_THRESHOLD:
            print(
                f"  WARNING: {key} is {section['word_count']} words "
                f"(>{SECTION_WORD_WARNING_THRESHOLD}) -- likely over-captured; "
                "check the end-boundary heading."
            )
    return paths


def run(
    html_path: Path, deal_slug: str, extra_continue_headings: list[str] | None = None
) -> dict[str, dict]:
    html = html_path.read_text(encoding="utf-8", errors="replace")
    sections = extract_sections(html, extra_continue_headings)
    save_sections(sections, DATA_SECTIONS / deal_slug)
    return sections


if __name__ == "__main__":
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/raw/splunk_inc_defm14a.html")
    slug = sys.argv[2] if len(sys.argv) > 2 else "splunk"
    run(path, slug)
