"""Automated deal discovery: scan EDGAR's quarterly form indexes for
DEFM14A/PREM14A/SC 14D9/SC TO-T/S-4 filings, group them into candidate
deals, and quick-check each one (section finder + consideration regex,
no LLM) to gauge how pipeline-ready it is.

    python -m src.discover                      # full scan, 2021 Q1 -> current quarter
    python -m src.discover --start-year 2023     # narrower range, for a faster pass

Writes to the deal_candidates table as it goes (upserted on
primary_accession, so a re-run or an interrupted run never duplicates or
re-fetches an already-checked deal) and prints a summary report at the
end (also saved to data/discovery/report.md).

Nothing here calls an LLM or writes to the main deals/events/proposals
tables -- this is purely a quick, free scan to find and triage
candidates for the real pipeline later.
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path
from typing import Optional

from src import sections as sections_module
from src.fetch import _throttled_get  # reuse the shared <=2 req/s rate limiter
from src.load_db import connect

# Some filings embed an enormous exhibit that streams slowly without
# ever tripping requests' own per-read timeout (a handful of reads, each
# comfortably under 30s, can still add up to many minutes for a huge
# file) -- a hard wall-clock deadline keeps one such filing from
# stalling the whole scan. Run via a thread so a blocking requests call
# can be abandoned once the deadline passes, even though the underlying
# socket isn't forcibly closed.
_FETCH_DEADLINE_SECONDS = 20.0
# A thread whose call exceeds the deadline is abandoned, not killed
# (Python can't forcibly stop a blocked thread), so a generous pool size
# means a handful of such leaked threads over a long scan can't exhaust
# it and start blocking fresh, otherwise-fast requests behind them.
_fetch_executor = ThreadPoolExecutor(max_workers=8)


def _get_with_deadline(url: str, max_seconds: float = _FETCH_DEADLINE_SECONDS):
    future = _fetch_executor.submit(_throttled_get, url)
    try:
        return future.result(timeout=max_seconds)
    except FutureTimeoutError as exc:
        raise TimeoutError(f"exceeded {max_seconds:.0f}s wall-clock deadline fetching {url}") from exc

DATA_DISCOVERY = Path(__file__).resolve().parent.parent / "data" / "discovery"
INDEX_CACHE_DIR = DATA_DISCOVERY / "indexes"
DOC_CACHE_DIR = DATA_DISCOVERY / "documents"

# Bare form types eligible to anchor a deal; "/A" amendments of these
# are tracked as linked documents, never promoted to primary. Lower rank
# wins. PREM14A and SC TO-T are last-resort primaries -- used only when
# a cluster never produced a DEFM14A/SC 14D9/S-4 (e.g. an abandoned deal
# that never went definitive), never when one of those is available.
PRIMARY_PREFERENCE = {
    "DEFM14A": 0,
    "SC 14D9": 1,
    "S-4": 2,
    "PREM14A": 3,
    "SC TO-T": 4,
}
TARGET_BASE_FORMS = set(PRIMARY_PREFERENCE)
CLUSTER_WINDOW_DAYS = 365


@dataclass
class FilingRow:
    form_type: str
    company_name: str
    cik: str
    date_filed: str
    file_name: str

    @property
    def accession(self) -> str:
        return Path(self.file_name).stem

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")


@dataclass
class DealCandidate:
    target_cik: str
    target_name: str
    primary: FilingRow
    linked: list[FilingRow] = field(default_factory=list)
    background_section_found: Optional[bool] = None
    background_word_count: Optional[int] = None
    consideration_type: Optional[str] = None
    consideration_value: Optional[float] = None
    section_finder_error: Optional[str] = None
    fetch_error: Optional[str] = None


def base_form_type(form_type: str) -> str:
    return form_type[:-2] if form_type.endswith("/A") else form_type


def is_amendment(form_type: str) -> bool:
    return form_type.endswith("/A")


def current_quarter() -> tuple[int, int]:
    today = date_cls.today()
    return today.year, (today.month - 1) // 3 + 1


def quarters_from(start_year: int, start_quarter: int, end_year: int, end_quarter: int) -> list[tuple[int, int]]:
    quarters = []
    year, quarter = start_year, start_quarter
    while (year, quarter) <= (end_year, end_quarter):
        quarters.append((year, quarter))
        quarter += 1
        if quarter > 4:
            quarter = 1
            year += 1
    return quarters


def fetch_form_index(year: int, quarter: int, force: bool = False) -> Path:
    INDEX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = INDEX_CACHE_DIR / f"{year}_QTR{quarter}_form.idx"
    if path.exists() and not force:
        return path
    url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
    response = _throttled_get(url)
    path.write_bytes(response.content)
    return path


# Each data row ends in "<CIK> <YYYY-MM-DD> <file_name>"; form type and
# company name are whatever precedes that, split at a fixed 12-char
# form-type column. The header's own column labels are NOT reliably
# aligned with the real data columns in these files (varies by quarter),
# so matching from the end of the line is more robust than trusting the
# header's stated offsets.
_ROW_RE = re.compile(r"(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$")


def parse_form_index(path: Path) -> list[FilingRow]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _ROW_RE.search(line)
        if not match:
            continue
        cik, date_filed, file_name = match.groups()
        prefix = line[: match.start(1)]
        form_type = prefix[:12].strip()
        company_name = prefix[12:].strip()
        if not form_type or not company_name:
            continue
        rows.append(FilingRow(form_type, company_name, cik, date_filed, file_name))
    return rows


def filter_relevant(rows: list[FilingRow]) -> list[FilingRow]:
    return [r for r in rows if base_form_type(r.form_type) in TARGET_BASE_FORMS]


def group_into_deals(filings: list[FilingRow]) -> list[DealCandidate]:
    by_cik: dict[str, list[FilingRow]] = {}
    for f in filings:
        by_cik.setdefault(f.cik, []).append(f)

    deals = []
    for cik, cik_filings in by_cik.items():
        cik_filings.sort(key=lambda f: f.date_filed)
        clusters: list[list[FilingRow]] = []
        for f in cik_filings:
            if clusters:
                last_date = date_cls.fromisoformat(clusters[-1][-1].date_filed)
                this_date = date_cls.fromisoformat(f.date_filed)
                if (this_date - last_date).days <= CLUSTER_WINDOW_DAYS:
                    clusters[-1].append(f)
                    continue
            clusters.append([f])

        for cluster in clusters:
            def sort_key(f: FilingRow) -> tuple:
                return (PRIMARY_PREFERENCE[base_form_type(f.form_type)], is_amendment(f.form_type), f.date_filed)

            primary = min(cluster, key=sort_key)
            linked = [f for f in cluster if f is not primary]
            deals.append(
                DealCandidate(
                    target_cik=cik,
                    target_name=primary.company_name,
                    primary=primary,
                    linked=linked,
                )
            )
    return deals


# Exchange ratios are near-always expressed with a decimal ("0.3521
# shares"); an authorized/outstanding share count in unrelated boilerplate
# almost never is, which keeps false positives low without needing to
# understand the surrounding sentence.
_CASH_PATTERNS = [
    re.compile(r"entitled to receive\s+\$([\d,]+\.\d{2})\s+in cash", re.IGNORECASE),
    re.compile(r"\$([\d,]+\.\d{2})\s+per share,?\s+(?:net to (?:the seller|you)\s+)?in cash", re.IGNORECASE),
    re.compile(r"\$([\d,]+\.\d{2})\s+in cash,?\s+without interest,?\s+(?:for|per) each share", re.IGNORECASE),
]
_STOCK_RATIO_RE = re.compile(r"\d+\.\d+\s+shares? of[^.\n]{0,80}common stock", re.IGNORECASE)


def extract_consideration(html: str) -> tuple[Optional[str], Optional[float]]:
    cash_value = None
    for pattern in _CASH_PATTERNS:
        match = pattern.search(html)
        if match:
            cash_value = float(match.group(1).replace(",", ""))
            break
    has_stock = _STOCK_RATIO_RE.search(html) is not None

    if cash_value is not None and has_stock:
        return "mixed", cash_value
    if cash_value is not None:
        return "cash", cash_value
    if has_stock:
        return "stock", None
    return "unknown", None


def _pick_primary_document(index_json: dict) -> Optional[str]:
    items = index_json.get("directory", {}).get("item", [])
    candidates = [
        it
        for it in items
        if it["name"].lower().endswith((".htm", ".html")) and "-index" not in it["name"].lower()
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda it: int(it.get("size") or 0), reverse=True)
    return candidates[0]["name"]


def quick_check_deal(deal: DealCandidate) -> None:
    """Fetches the primary document (cached) and runs the section finder
    and consideration regex against it. Mutates `deal` in place; never
    raises -- failures are recorded on the deal, not propagated, so one
    bad filing can't stop the scan.
    """
    cik_int = int(deal.target_cik)
    accession_nodash = deal.primary.accession_nodash
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"

    try:
        index_json = _get_with_deadline(index_url).json()
    except Exception as exc:
        deal.fetch_error = f"index lookup failed ({type(exc).__name__})"
        return

    doc_name = _pick_primary_document(index_json)
    if not doc_name:
        deal.fetch_error = "no primary document found in filing index"
        return

    DOC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = DOC_CACHE_DIR / f"{deal.target_cik}_{accession_nodash}.html"
    if cache_path.exists():
        html = cache_path.read_text(encoding="utf-8", errors="replace")
    else:
        doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{doc_name}"
        try:
            html_bytes = _get_with_deadline(doc_url, max_seconds=45.0).content
        except Exception as exc:
            deal.fetch_error = f"document fetch failed ({type(exc).__name__})"
            return
        cache_path.write_bytes(html_bytes)
        html = html_bytes.decode("utf-8", errors="replace")

    try:
        found = sections_module.extract_sections(html)
        if "background_of_the_merger" in found:
            deal.background_section_found = True
            deal.background_word_count = found["background_of_the_merger"]["word_count"]
        else:
            deal.background_section_found = False
            deal.section_finder_error = "heading not found"
    except Exception as exc:
        deal.background_section_found = False
        deal.section_finder_error = f"section finder raised ({type(exc).__name__})"

    deal.consideration_type, deal.consideration_value = extract_consideration(html)


def upsert_deal_candidate(conn, deal: DealCandidate) -> None:
    linked_json = json.dumps(
        [
            {
                "form_type": f.form_type,
                "accession": f.accession,
                "date_filed": f.date_filed,
                "file_name": f.file_name,
            }
            for f in deal.linked
        ]
    )
    conn.execute(
        """
        INSERT INTO deal_candidates (
            target_cik, target_name, primary_form_type, primary_accession,
            primary_filed_date, primary_file_name, linked_filings,
            background_section_found, background_word_count,
            consideration_type, consideration_value,
            section_finder_error, fetch_error, checked_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (primary_accession) DO UPDATE SET
            target_name = EXCLUDED.target_name,
            linked_filings = EXCLUDED.linked_filings,
            background_section_found = EXCLUDED.background_section_found,
            background_word_count = EXCLUDED.background_word_count,
            consideration_type = EXCLUDED.consideration_type,
            consideration_value = EXCLUDED.consideration_value,
            section_finder_error = EXCLUDED.section_finder_error,
            fetch_error = EXCLUDED.fetch_error,
            checked_at = now()
        """,
        (
            deal.target_cik,
            deal.target_name,
            deal.primary.form_type,
            deal.primary.accession,
            deal.primary.date_filed,
            deal.primary.file_name,
            linked_json,
            deal.background_section_found,
            deal.background_word_count,
            deal.consideration_type,
            deal.consideration_value,
            deal.section_finder_error,
            deal.fetch_error,
        ),
    )


def already_checked(conn, accession: str) -> bool:
    row = conn.execute(
        "SELECT checked_at FROM deal_candidates WHERE primary_accession = %s", (accession,)
    ).fetchone()
    return row is not None and row[0] is not None


def generate_report(conn) -> str:
    lines = ["# Deal discovery report", ""]

    total = conn.execute("SELECT count(*) FROM deal_candidates").fetchone()[0]
    checked = conn.execute("SELECT count(*) FROM deal_candidates WHERE checked_at IS NOT NULL").fetchone()[0]
    found = conn.execute(
        "SELECT count(*) FROM deal_candidates WHERE background_section_found = true"
    ).fetchone()[0]
    all_cash = conn.execute(
        "SELECT count(*) FROM deal_candidates WHERE consideration_type = 'cash'"
    ).fetchone()[0]

    lines.append(f"Total candidate deals: {total}")
    lines.append(f"Checked: {checked}")
    if checked:
        lines.append(f"Background section found: {found}/{checked} ({found / checked:.0%})")
        lines.append(f"All-cash consideration: {all_cash}/{checked} ({all_cash / checked:.0%})")
    lines.append("")

    lines.append("## Totals by year and primary form type")
    rows = conn.execute(
        """
        SELECT date_part('year', primary_filed_date)::int AS year, primary_form_type, count(*)
        FROM deal_candidates GROUP BY year, primary_form_type ORDER BY year, primary_form_type
        """
    ).fetchall()
    lines.append("| year | form type | count |")
    lines.append("|------|-----------|-------|")
    for year, form_type, count in rows:
        lines.append(f"| {year} | {form_type} | {count} |")
    lines.append("")

    lines.append("## 20 most common sectioning-failure reasons")
    rows = conn.execute(
        """
        SELECT coalesce(fetch_error, section_finder_error) AS reason, count(*)
        FROM deal_candidates
        WHERE checked_at IS NOT NULL AND background_section_found IS NOT TRUE
        GROUP BY reason ORDER BY count(*) DESC LIMIT 20
        """
    ).fetchall()
    lines.append("| reason | count |")
    lines.append("|--------|-------|")
    for reason, count in rows:
        lines.append(f"| {reason or '(unknown)'} | {count} |")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan EDGAR for merger/tender-offer deal candidates.")
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--start-quarter", type=int, default=1)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--end-quarter", type=int, default=None)
    args = parser.parse_args()

    end_year, end_quarter = (args.end_year, args.end_quarter) if args.end_year else current_quarter()

    all_filings: list[FilingRow] = []
    for year, quarter in quarters_from(args.start_year, args.start_quarter, end_year, end_quarter):
        idx_path = fetch_form_index(year, quarter)
        rows = parse_form_index(idx_path)
        relevant = filter_relevant(rows)
        all_filings.extend(relevant)
        print(f"{year} Q{quarter}: {len(rows)} total rows, {len(relevant)} relevant")

    deals = group_into_deals(all_filings)
    print(f"\nGrouped {len(all_filings)} filings into {len(deals)} candidate deals")

    with connect() as conn:
        for i, deal in enumerate(deals, 1):
            if already_checked(conn, deal.primary.accession):
                continue
            quick_check_deal(deal)
            upsert_deal_candidate(conn, deal)
            conn.commit()
            if i % 25 == 0 or i == len(deals):
                print(f"  checked {i}/{len(deals)}")

        report = generate_report(conn)

    DATA_DISCOVERY.mkdir(parents=True, exist_ok=True)
    (DATA_DISCOVERY / "report.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
