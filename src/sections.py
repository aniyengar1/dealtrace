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

# Some filing agents (e.g. Coupa's) encode smart quotes/dashes as decimal
# numeric character references in the 128-159 range -- &#147; for a left
# curly quote, &#146; for a right single quote -- which are legacy
# Windows-1252 byte codes, not literal Unicode code points. Real browsers
# decode these through HTML5's backward-compatibility override table
# (the same one Python's html.unescape implements); lxml doesn't, so
# BeautifulSoup(html, "lxml") resolves &#147; to the raw C1 control
# character U+0093 instead of the curly quote U+201C it actually stands
# for. Pre-resolve just this narrow range before lxml ever sees it,
# leaving every other entity (&amp;, &lt;, &nbsp;, named entities, numeric
# refs outside 128-159) untouched for lxml's normal handling.
_LEGACY_CP1252_OVERRIDES = {
    128: "€", 130: "‚", 131: "ƒ", 132: "„", 133: "…",
    134: "†", 135: "‡", 136: "ˆ", 137: "‰", 138: "Š",
    139: "‹", 140: "Œ", 142: "Ž", 145: "‘", 146: "’",
    147: "“", 148: "”", 149: "•", 150: "–", 151: "—",
    152: "˜", 153: "™", 154: "š", 155: "›", 156: "œ",
    158: "ž", 159: "Ÿ",
}
_LEGACY_CHARREF_RE = re.compile(r"&#(?:0*(1[2-5]\d)|[xX]0*([89a-bA-B][0-9a-fA-F]));")


def _decode_legacy_cp1252_charrefs(html: str) -> str:
    def _sub(match: "re.Match") -> str:
        code = int(match.group(1)) if match.group(1) else int(match.group(2), 16)
        return _LEGACY_CP1252_OVERRIDES.get(code, chr(code))

    return _LEGACY_CHARREF_RE.sub(_sub, html)

SECTION_SPECS = {
    # Tender-offer filings (SC 14D9/SC TO-T) use "Background of the
    # Offer" (or, when a tender offer is itself followed by a back-end
    # merger, "...the Offer and the Merger") instead of "...the Merger"
    # -- found while building the EDGAR discovery scan (src/discover.py),
    # which checks both DEFM14A-style and tender-offer-style filings.
    "background_of_the_merger": [
        r"^Background of the Merger$",
        r"^Background of the Offer$",
        r"^Background of the Offer and the Merger$",
    ],
    "management_projections": [
        r"^Certain Unaudited Prospective Financial Information$",
        r"^Unaudited Prospective Financial Information$",
        r"^Management Projections$",
        r"^Certain Financial Projections$",
        r"^Projected Financial Information$",
        r"^Financial Forecasts$",
        # Found while re-sectioning Coupa/New Relic/Activision, which
        # don't use any of the patterns above: Coupa and Activision each
        # call it "Certain Financial Forecasts"/"Management Forecasts"
        # instead of "Financial Forecasts" outright, and New Relic's own
        # heading is "Summary of Management Projections", not the bare
        # "Management Projections" above.
        r"^Certain Financial Forecasts$",
        r"^Management Forecasts$",
        r"^Summary of Management Projections$",
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
    __slots__ = ("id", "text", "level", "looks_like_heading")

    def __init__(
        self, para_id: str, text: str, level: int | None, looks_like_heading: bool = False
    ):
        self.id = para_id
        self.text = text
        self.level = level
        # Precomputed candidate-heading flag for the fallback parser (see
        # _extract_sections_fallback) -- never read by the primary h1-h5
        # path, so computing it costs nothing for filings that don't need
        # it and can't change their output.
        self.looks_like_heading = looks_like_heading

    def to_dict(self) -> dict:
        return {"id": self.id, "text": self.text}


_ZERO_WIDTH_RE = re.compile(r"[​ ]")

_STYLE_TAG_NAMES = ("b", "strong", "i", "em", "u")
_BOLD_STYLE_RE = re.compile(r"font-weight\s*:\s*(bold|[6-9]00)", re.IGNORECASE)
_UNDERLINE_STYLE_RE = re.compile(r"text-decoration\s*:\s*underline", re.IGNORECASE)

# Standard DEFM14A chapter names, used by the fallback parser (no semantic
# heading markup) for two things: recognizing a block of text as a
# candidate heading at all (the "exact match to a known name" trigger,
# alongside bold/italic/underline/all-caps styling), and recognizing the
# next occurrence of one as the end of whatever section came before it.
# Deliberately loose (.search, not anchored) since real headings carry
# extra words around the core phrase (e.g. "Recommendation of the Twitter
# Board AND REASONS FOR THE MERGER" combines two of these into one
# heading) and can have embedded line breaks from hard-wrapped source HTML.
_KNOWN_STANDARD_HEADING_RE = re.compile(
    r"background of the merger"
    r"|recommendation of .{0,40}board"
    r"|reasons for the merger"
    r"|opinion of "
    r"|certain unaudited prospective financial information"
    r"|unaudited prospective financial information"
    r"|management projections"
    r"|certain financial projections"
    r"|^projections$"
    r"|interests of .{0,60}directors and executive officers"
    r"|financing of the merger"
    r"|^financing$"
    r"|regulatory approvals"
    r"|^the merger agreement$",
    re.IGNORECASE,
)


def _tag_is_styled_like_heading(tag) -> bool:
    if tag.find(_STYLE_TAG_NAMES):
        return True
    style = tag.get("style") or ""
    return bool(_BOLD_STYLE_RE.search(style) or _UNDERLINE_STYLE_RE.search(style))


def _normalize_for_heading_match(text: str) -> str:
    """Collapse newline/tab/multi-space runs for heading pattern matching
    ONLY -- never applied to stored paragraph text, which can carry
    intentional non-breaking spaces (e.g. "November[nbsp]15, 2021") that
    must survive untouched for downstream quote verification.
    """
    return re.sub(r"[ \t\r\n]+", " ", text).strip()


def _looks_like_heading_candidate(tag, text: str) -> bool:
    """A fallback-parser candidate heading: short, not a sentence, and
    either visually distinct (bold/italic/underline/all-caps) or an exact
    match for a name real DEFM14A chapters commonly use. The latter
    catches a real heading whose styling this check doesn't recognize;
    callers still have to separately confirm it's followed by substantial
    prose and not a table-of-contents listing (see _fallback_best_match).
    """
    if not text or len(text.split()) > 15 or text.rstrip().endswith("."):
        return False
    if _tag_is_styled_like_heading(tag):
        return True
    if text.isupper():
        return True
    return bool(_KNOWN_STANDARD_HEADING_RE.search(_normalize_for_heading_match(text)))


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
    html = _decode_legacy_cp1252_charrefs(html)
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
        paragraphs.append(
            Paragraph(f"p{counter:05d}", text, level, _looks_like_heading_candidate(tag, text))
        )

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


def _build_continue_re(extra_continue_headings: list[str] | None) -> "re.Pattern":
    if not extra_continue_headings:
        return OPINION_SUBSECTION_RE
    extra_pattern = "|".join(f"^{re.escape(h)}$" for h in extra_continue_headings)
    return re.compile(f"{OPINION_SUBSECTION_RE.pattern}|{extra_pattern}", re.IGNORECASE)


def _section_dict(key: str, heading_para: Paragraph, body: list[Paragraph], word_count: int) -> dict:
    return {
        "section_key": key,
        "heading_text": heading_para.text,
        "heading_paragraph_id": heading_para.id,
        "word_count": word_count,
        "paragraphs": [p.to_dict() for p in body],
    }


def _extract_sections_primary(paragraphs: list[Paragraph], continue_re: "re.Pattern") -> dict[str, dict]:
    """The original (unchanged) logic: section boundaries from h1-h5
    heading depth. Only runs when parse_paragraphs found at least one
    real heading -- see extract_sections.
    """
    sections: dict[str, dict] = {}

    for key, patterns in SECTION_SPECS.items():
        match = _best_match(paragraphs, patterns)
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        sections[key] = _section_dict(key, heading_para, body, word_count)

    for heading_text in find_opinion_headings(paragraphs):
        match = _best_match(paragraphs, [re.escape(heading_text)], continue_re=continue_re)
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        key = f"opinion_of_{_slugify(heading_text.replace('Opinion of', ''))}"
        sections[key] = _section_dict(key, heading_para, body, word_count)

    return sections


_FALLBACK_MIN_PROSE_WORDS = 300


def _fallback_word_count_between(paragraphs: list[Paragraph], start_idx: int, end_idx: int) -> int:
    return sum(len(paragraphs[j].text.split()) for j in range(start_idx + 1, end_idx))


def _fallback_find_end(
    paragraphs: list[Paragraph],
    candidate_indices: list[int],
    start_idx: int,
    continue_re: "re.Pattern | None" = None,
) -> int:
    """First candidate index after start_idx matching a known standard
    heading (and not continue_re); len(paragraphs) if none found. Candidate
    indices that match neither -- a quoted letter's signature block, a
    person's name, an all-caps defined term -- are silently skipped rather
    than ending the section, since only a recognized chapter name is
    trusted as a real boundary here (there's no heading-depth signal to
    fall back on in this parser).
    """
    for ci in candidate_indices:
        if ci <= start_idx:
            continue
        text = _normalize_for_heading_match(paragraphs[ci].text)
        if continue_re and continue_re.search(text):
            continue
        if _KNOWN_STANDARD_HEADING_RE.search(text):
            return ci
    return len(paragraphs)


def _fallback_best_match(
    paragraphs: list[Paragraph],
    candidate_indices: list[int],
    patterns: list[str],
    continue_re: "re.Pattern | None" = None,
) -> tuple[int, int, int] | None:
    """Like _best_match, but driven by candidate_indices + known-heading
    text matching instead of heading depth, and requiring at least
    _FALLBACK_MIN_PROSE_WORDS of body content -- a table-of-contents
    listing of the same heading text is immediately followed by another
    TOC entry (near-zero words before it), which this filters out without
    needing to specially detect "this is the TOC" at all.
    """
    compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
    best = None
    for ci in candidate_indices:
        text = _normalize_for_heading_match(paragraphs[ci].text)
        if not any(c.search(text) for c in compiled):
            continue
        end_idx = _fallback_find_end(paragraphs, candidate_indices, ci, continue_re)
        word_count = _fallback_word_count_between(paragraphs, ci, end_idx)
        if word_count < _FALLBACK_MIN_PROSE_WORDS:
            continue
        if best is None or word_count > best[2]:
            best = (ci, end_idx, word_count)
    return best


_PAGE_REFERENCE_RE = re.compile(r"\s*\(\s*(?:see\s+)?page\s+\d+\s*\)\s*$", re.IGNORECASE)


def _strip_page_reference(text: str) -> str:
    """Drop a trailing "(page 41)"-style cross-reference annotation.

    A short "Summary" chapter in some filings lists "Opinion of Qatalyst
    Partners (page 41)" as a cross-reference to the real heading further
    in; without stripping this, it's a different exact string from the
    real "Opinion of Qatalyst Partners" heading and gets treated as a
    second, separate advisor. Stripping it collapses both onto the same
    canonical text, and _fallback_best_match's own word-count/minimum-
    prose logic (same mechanism that already separates a table-of-
    contents listing from the real heading) then picks the real,
    substantial occurrence over this short stub on its own.
    """
    return _PAGE_REFERENCE_RE.sub("", text).strip()


def _fallback_find_opinion_headings(paragraphs: list[Paragraph], candidate_indices: list[int]) -> list[str]:
    seen = []
    for ci in candidate_indices:
        text = _normalize_for_heading_match(paragraphs[ci].text)
        if OPINION_HEADING_RE.match(text):
            canonical = _strip_page_reference(text)
            if canonical not in seen:
                seen.append(canonical)
    return seen


def _extract_sections_fallback(paragraphs: list[Paragraph], continue_re: "re.Pattern") -> dict[str, dict]:
    """Section detection for filings with no semantic h1-h5 heading markup
    at all (used only when parse_paragraphs found zero real headings --
    see extract_sections). Candidate headings are short, non-sentence
    blocks that are visually distinct or an exact known chapter name (see
    _looks_like_heading_candidate); a section ends at the next candidate
    that names a *known* standard chapter (_KNOWN_STANDARD_HEADING_RE),
    not just the next candidate of any kind, since most candidates in a
    markup-less filing turn out to be names, salutations, and other
    short bold text from quoted correspondence rather than real headings.
    """
    candidate_indices = [i for i, p in enumerate(paragraphs) if p.looks_like_heading]
    sections: dict[str, dict] = {}

    for key, patterns in SECTION_SPECS.items():
        match = _fallback_best_match(paragraphs, candidate_indices, patterns)
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        sections[key] = _section_dict(key, heading_para, body, word_count)

    for heading_text in _fallback_find_opinion_headings(paragraphs, candidate_indices):
        match = _fallback_best_match(
            paragraphs, candidate_indices, [re.escape(heading_text)], continue_re=continue_re
        )
        if match is None:
            continue
        start_idx, end_idx, word_count = match
        heading_para = paragraphs[start_idx]
        body = paragraphs[start_idx + 1 : end_idx]
        key = f"opinion_of_{_slugify(heading_text.replace('Opinion of', ''))}"
        sections[key] = _section_dict(key, heading_para, body, word_count)

    return sections


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

    If parse_paragraphs finds zero real (h1-h5) headings anywhere in the
    document, this is a filing that uses a different, markup-less
    template, and the whole document falls through to
    _extract_sections_fallback. Filings with real headings never touch
    that path, so this can't change their output.
    """
    paragraphs = parse_paragraphs(html)
    continue_re = _build_continue_re(extra_continue_headings)

    if any(p.level is not None for p in paragraphs):
        return _extract_sections_primary(paragraphs, continue_re)
    return _extract_sections_fallback(paragraphs, continue_re)


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
