"""Classify deal_candidates (no LLM) and link SC TO-T filings to their
matching SC 14D9 when a tender offer's bidder, not its target, is the
CIK form.idx attributed the filing to.

    python -m src.classify

For every unclassified deal_candidates row:
  1. Fetch the filing's SGML header (-index-headers.html, lightweight --
     a few KB, not the full document) to find the TRUE subject company
     CIK and SIC code. SC TO-T is filed by the bidder, so form.idx's own
     CIK column sometimes names the bidder, not the target -- group_into_deals
     already prefers SC 14D9 over SC TO-T within the same CIK cluster, so
     any row that's STILL SC-TO-T-primaried here got that way because its
     true target's CIK differs from the bidder's, and the target almost
     always already has its own, correctly-clustered SC 14D9 row.
  2. If so, fold this row into that SC 14D9 row (as a linked filing) and
     delete it -- it's the same real deal counted once, not twice.
  3. Classify the surviving row from SIC code + text signals in whatever
     was already cached during the quick-check phase (no new document
     fetches): SIC 6770 or trust-account + blank-check/SPAC language ->
     spac_de_spac; debt/warrant exchange, reorganization, going-private,
     or a depository-institution SIC -> other; otherwise ->
     public_company_acquisition.
"""

import json
import re
from pathlib import Path
from typing import Optional

from src.discover import DATA_DISCOVERY, DOC_CACHE_DIR, _get_with_deadline
from src.load_db import connect

HEADER_CACHE_DIR = DATA_DISCOVERY / "headers"

# The SGML header wraps a <SUBJECT-COMPANY> block (tender offers: the
# target) and one or more <FILER> blocks (everything else: the filer IS
# the subject, e.g. a DEFM14A filed by the target about itself).
_SUBJECT_COMPANY_RE = re.compile(r"<SUBJECT-COMPANY>.*?<CIK>0*(\d+).*?<ASSIGNED-SIC>(\d+)", re.DOTALL)
_FIRST_FILER_RE = re.compile(r"<FILER>.*?<CIK>0*(\d+).*?<ASSIGNED-SIC>(\d+)", re.DOTALL)

SPAC_SIC = {"6770"}
_TRUST_ACCOUNT_RE = re.compile(r"\btrust account\b", re.IGNORECASE)
_BLANK_CHECK_RE = re.compile(r"\bblank check\b|\bspecial purpose acquisition\b|\bde-spac\b", re.IGNORECASE)

# Order matters only for which reason gets reported when a document
# happens to match more than one -- all map to "other" regardless.
_OTHER_SIGNALS: list[tuple[str, re.Pattern]] = [
    (
        "debt_or_warrant_exchange",
        re.compile(r"exchange offer for[^.\n]{0,60}(notes|debentures|warrants)", re.IGNORECASE),
    ),
    (
        "reorganization",
        re.compile(r"agreement and plan of reorganization|holding company reorganization", re.IGNORECASE),
    ),
    (
        "going_private_squeeze_out",
        re.compile(r"rule 13e-3|going[- ]private transaction", re.IGNORECASE),
    ),
]


def fetch_filing_header(cik: int, accession: str) -> Optional[dict]:
    """Returns {"cik": ..., "sic": ...} for the filing's true subject
    company, or None if the header couldn't be fetched/parsed."""
    accession_nodash = accession.replace("-", "")
    cache_path = HEADER_CACHE_DIR / f"{accession_nodash}.html"
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8", errors="replace")
    else:
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{accession}-index-headers.html"
        try:
            text = _get_with_deadline(url).text
        except Exception:
            return None
        HEADER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text)

    match = _SUBJECT_COMPANY_RE.search(text) or _FIRST_FILER_RE.search(text)
    if not match:
        return None
    return {"cik": match.group(1), "sic": match.group(2)}


def classify_deal(sic: Optional[str], html: Optional[str]) -> tuple[str, str]:
    if sic in SPAC_SIC:
        return "spac_de_spac", f"SIC {sic} (blank check)"

    if html:
        if _TRUST_ACCOUNT_RE.search(html) and _BLANK_CHECK_RE.search(html):
            return "spac_de_spac", "trust account + blank check/SPAC language"
        for reason, pattern in _OTHER_SIGNALS:
            if pattern.search(html):
                return "other", reason

    if sic and sic.startswith("60"):
        return "other", f"depository institution (SIC {sic})"

    return "public_company_acquisition", "default"


def find_matching_sc14d9(conn, subject_cik: str, filed_date: str, exclude_accession: str) -> Optional[tuple]:
    return conn.execute(
        """
        SELECT id, linked_filings FROM deal_candidates
        WHERE target_cik = %s AND primary_form_type = 'SC 14D9'
          AND primary_accession != %s
          AND abs(primary_filed_date - %s::date) <= 60
        LIMIT 1
        """,
        (subject_cik, exclude_accession, filed_date),
    ).fetchone()


def _cached_document_html(target_cik: str, accession: str) -> Optional[str]:
    cache_path = DOC_CACHE_DIR / f"{target_cik}_{accession.replace('-', '')}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    return None


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, target_cik, primary_form_type, primary_accession, primary_filed_date
            FROM deal_candidates WHERE classification IS NULL ORDER BY primary_filed_date
            """
        ).fetchall()
        print(f"{len(rows)} deals to classify")

        linked_count = 0
        for i, (row_id, target_cik, form_type, accession, filed_date) in enumerate(rows, 1):
            header = fetch_filing_header(int(target_cik), accession)
            subject_cik = header["cik"] if header else None
            subject_sic = header["sic"] if header else None

            if form_type == "SC TO-T" and subject_cik and subject_cik != target_cik:
                match = find_matching_sc14d9(conn, subject_cik, str(filed_date), accession)
                if match:
                    match_id, match_linked_raw = match
                    match_linked = match_linked_raw if isinstance(match_linked_raw, list) else json.loads(match_linked_raw)
                    match_linked.append(
                        {
                            "form_type": "SC TO-T",
                            "accession": accession,
                            "date_filed": str(filed_date),
                            "note": "bidder's own CIK in form.idx; true subject is this row",
                        }
                    )
                    conn.execute(
                        "UPDATE deal_candidates SET linked_filings = %s WHERE id = %s",
                        (json.dumps(match_linked), match_id),
                    )
                    conn.execute("DELETE FROM deal_candidates WHERE id = %s", (row_id,))
                    conn.commit()
                    linked_count += 1
                    if i % 100 == 0:
                        print(f"  {i}/{len(rows)} ({linked_count} linked so far)")
                    continue

            html = _cached_document_html(target_cik, accession)
            classification, reason = classify_deal(subject_sic, html)
            conn.execute(
                """
                UPDATE deal_candidates
                SET subject_cik = %s, subject_sic = %s, classification = %s, classification_reason = %s
                WHERE id = %s
                """,
                (subject_cik, subject_sic, classification, reason, row_id),
            )
            conn.commit()
            if i % 100 == 0:
                print(f"  {i}/{len(rows)} ({linked_count} linked so far)")

        print(f"\nDone. {linked_count} SC TO-T rows linked into their target's SC 14D9 and removed.")


if __name__ == "__main__":
    main()
