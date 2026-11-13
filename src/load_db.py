"""Load pipeline output (sections + extraction runs) into Postgres.

    python -m src.load_db                 # load every deal in DEALS
    python -m src.load_db splunk coupa    # load specific deals

Idempotent: deals/paragraphs/extraction_runs are upserted on their natural
key; Event/Proposal/ValuationAnalysis rows are upserted on
(run_id, content_hash), a sha256 of the record's own fields -- re-running
against the same (immutable, never-overwritten) run folder is always a
no-op, and a human's review_status edit is never clobbered by a reload.

All access goes through DATABASE_URL (see get_database_url) so pointing
this at Supabase instead of local Postgres later is a config change only
-- nothing here hardcodes a host, database name, or local-only behavior.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg

from src.env import load_env
from src.run import DEALS

load_env()

DATA_SECTIONS = Path(__file__).resolve().parent.parent / "data" / "sections"
DATA_RUNS = Path(__file__).resolve().parent.parent / "data" / "output" / "runs"

TABLES = ("deals", "paragraphs", "extraction_runs", "events", "proposals", "valuations")


def get_database_url() -> str:
    return os.environ["DATABASE_URL"]


def connect(database_url: Optional[str] = None) -> psycopg.Connection:
    return psycopg.connect(database_url or get_database_url())


def upsert_deal(conn: psycopg.Connection, slug: str, deal: dict) -> str:
    row = conn.execute(
        """
        INSERT INTO deals (slug, deal_name, target, acquirer, search_term)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (slug) DO UPDATE SET
            deal_name = EXCLUDED.deal_name,
            target = EXCLUDED.target,
            acquirer = EXCLUDED.acquirer,
            search_term = EXCLUDED.search_term
        RETURNING id
        """,
        (slug, deal["deal_name"], deal["target"], deal["acquirer"], deal["search_term"]),
    ).fetchone()
    return row[0]


def upsert_paragraph(
    conn: psycopg.Connection,
    deal_id: str,
    paragraph_id: str,
    section_key: str,
    level: Optional[int],
    text: str,
) -> None:
    conn.execute(
        """
        INSERT INTO paragraphs (deal_id, paragraph_id, section_key, level, text)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (deal_id, paragraph_id) DO UPDATE SET
            section_key = EXCLUDED.section_key,
            level = EXCLUDED.level,
            text = EXCLUDED.text
        """,
        (deal_id, paragraph_id, section_key, level, text),
    )


def load_paragraphs_from_sections(conn: psycopg.Connection, deal_id: str, slug: str) -> int:
    """Disk I/O wrapper: upserts every paragraph from every data/sections/<slug>/*.json file."""
    section_dir = DATA_SECTIONS / slug
    if not section_dir.is_dir():
        return 0
    n = 0
    for section_path in sorted(section_dir.glob("*.json")):
        section_key = section_path.stem
        section = json.loads(section_path.read_text())
        for p in section["paragraphs"]:
            upsert_paragraph(conn, deal_id, p["id"], section_key, p.get("level"), p["text"])
            n += 1
    return n


# Matches the folder names _run_id() in validate.py writes:
# "<timestamp>_<deal_slug>_<model>_<prompt_version>". The slug is supplied
# by the caller (never guessed from the string) since slugs like
# "new_relic" contain underscores that would otherwise be ambiguous; model
# and prompt_version are then split on prompt_version's one fixed
# convention -- every prompt_version used so far starts with "v" + a
# digit, and models never do, so that's an unambiguous boundary.
def _run_dir_pattern(slug: str) -> re.Pattern:
    return re.compile(
        rf"^(?P<timestamp>\d{{8}}T\d{{6}}Z)_{re.escape(slug)}_(?P<model>.+)_(?P<prompt_version>v\d[\w-]*)$"
    )


def parse_run_dir_name(slug: str, run_dir_name: str) -> dict:
    match = _run_dir_pattern(slug).match(run_dir_name)
    if match is None:
        raise ValueError(f"run dir name doesn't match the expected pattern: {run_dir_name!r}")
    started_at = datetime.strptime(match.group("timestamp"), "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    )
    return {
        "started_at": started_at,
        "model": match.group("model"),
        "prompt_version": match.group("prompt_version"),
    }


def find_latest_run_dir(slug: str) -> Optional[Path]:
    """Most recent data/output/runs/ folder for this deal, by timestamp. None if
    the deal has no completed run yet."""
    if not DATA_RUNS.is_dir():
        return None
    pattern = _run_dir_pattern(slug)
    candidates = [
        (match.group("timestamp"), run_dir)
        for run_dir in DATA_RUNS.iterdir()
        if run_dir.is_dir() and (match := pattern.match(run_dir.name))
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def upsert_extraction_run(
    conn: psycopg.Connection, deal_id: str, slug: str, run_dir_name: str
) -> str:
    meta = parse_run_dir_name(slug, run_dir_name)
    row = conn.execute(
        """
        INSERT INTO extraction_runs (deal_id, run_dir, model, prompt_version, started_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (run_dir) DO UPDATE SET
            model = EXCLUDED.model,
            prompt_version = EXCLUDED.prompt_version,
            started_at = EXCLUDED.started_at
        RETURNING id
        """,
        (deal_id, run_dir_name, meta["model"], meta["prompt_version"], meta["started_at"]),
    ).fetchone()
    return row[0]


def content_hash(record: dict) -> str:
    """Stable identity for a record's own fields -- excludes validation
    metadata (passed/failure_reasons) so re-validating in place (rather
    than writing a new run folder) wouldn't change a record's identity."""
    canonical = json.dumps(record, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def upsert_event(conn: psycopg.Connection, run_id: str, record: dict, passed: bool, failure_reasons: list[str]) -> bool:
    """Returns True if a new row was inserted, False if it already existed."""
    cur = conn.execute(
        """
        INSERT INTO events (
            run_id, content_hash, date_text, date_start, date_end,
            date_precision, event_type, parties, summary,
            source_paragraph_ids, source_quotes, passed, failure_reasons
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id, content_hash) DO NOTHING
        """,
        (
            run_id,
            content_hash(record),
            record["date_text"],
            record.get("date_start"),
            record.get("date_end"),
            record["date_precision"],
            record["event_type"],
            record.get("parties", []),
            record["summary"],
            record.get("source_paragraph_ids", []),
            record.get("source_quotes", []),
            passed,
            failure_reasons,
        ),
    )
    return cur.rowcount > 0


def upsert_proposal(conn: psycopg.Connection, run_id: str, record: dict, passed: bool, failure_reasons: list[str]) -> bool:
    cur = conn.execute(
        """
        INSERT INTO proposals (
            run_id, content_hash, date_text, date_resolved, proposer, recipient,
            price_low, price_high, premium_pct, currency, consideration_type,
            proposal_kind, status, source_paragraph_ids, source_quotes,
            passed, failure_reasons
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id, content_hash) DO NOTHING
        """,
        (
            run_id,
            content_hash(record),
            record["date"],
            record.get("date_resolved"),
            record["proposer"],
            record["recipient"],
            record.get("price_low"),
            record.get("price_high"),
            record.get("premium_pct"),
            record.get("currency"),
            record["consideration_type"],
            record["proposal_kind"],
            record["status"],
            record.get("source_paragraph_ids", []),
            record.get("source_quotes", []),
            passed,
            failure_reasons,
        ),
    )
    return cur.rowcount > 0


def upsert_valuation(conn: psycopg.Connection, run_id: str, record: dict, passed: bool, failure_reasons: list[str]) -> bool:
    cur = conn.execute(
        """
        INSERT INTO valuations (
            run_id, content_hash, advisor, method, metric,
            multiple_low, multiple_high, implied_price_low, implied_price_high,
            key_assumptions, source_paragraph_ids, source_quotes, passed, failure_reasons
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id, content_hash) DO NOTHING
        """,
        (
            run_id,
            content_hash(record),
            record["advisor"],
            record["method"],
            record["metric"],
            record.get("multiple_low"),
            record.get("multiple_high"),
            record.get("implied_price_low"),
            record.get("implied_price_high"),
            record.get("key_assumptions", []),
            record.get("source_paragraph_ids", []),
            record.get("source_quotes", []),
            passed,
            failure_reasons,
        ),
    )
    return cur.rowcount > 0


_UPSERT_BY_RECORD_TYPE = {
    "Event": upsert_event,
    "Proposal": upsert_proposal,
    "ValuationAnalysis": upsert_valuation,
}


def load_records_from_results(conn: psycopg.Connection, run_id: str, results: list[dict]) -> dict[str, int]:
    """Loads an already-parsed <slug>_extraction.json's record list. Returns
    counts of rows newly inserted (not total seen) per record type."""
    counts = {"Event": 0, "Proposal": 0, "ValuationAnalysis": 0}
    for r in results:
        upsert = _UPSERT_BY_RECORD_TYPE[r["record_type"]]
        inserted = upsert(conn, run_id, r["record"], r["passed"], r.get("failure_reasons", []))
        if inserted:
            counts[r["record_type"]] += 1
    return counts


def load_extraction_run(conn: psycopg.Connection, deal_id: str, slug: str, run_dir: Path) -> dict:
    """Disk I/O wrapper: upserts the run row, then loads its extraction.json."""
    run_id = upsert_extraction_run(conn, deal_id, slug, run_dir.name)
    extraction_path = run_dir / f"{slug}_extraction.json"
    results = json.loads(extraction_path.read_text())
    counts = load_records_from_results(conn, run_id, results)
    return {"run_dir": run_dir.name, **counts}


def load_deal(conn: psycopg.Connection, slug: str) -> dict:
    if slug not in DEALS:
        raise ValueError(f"unknown deal '{slug}'. Known deals: {list(DEALS)}")
    deal = DEALS[slug]
    deal_id = upsert_deal(conn, slug, deal)
    n_paragraphs = load_paragraphs_from_sections(conn, deal_id, slug)

    run_dir = find_latest_run_dir(slug)
    if run_dir is None:
        return {"slug": slug, "paragraphs": n_paragraphs}

    run_result = load_extraction_run(conn, deal_id, slug, run_dir)
    return {"slug": slug, "paragraphs": n_paragraphs, **run_result}


def report_counts(conn: psycopg.Connection) -> dict[str, int]:
    counts = {}
    for table in TABLES:
        counts[table] = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return counts


def main(slugs: Optional[list[str]] = None) -> None:
    slugs = slugs or list(DEALS)
    with connect() as conn:
        for slug in slugs:
            result = load_deal(conn, slug)
            conn.commit()
            if "run_dir" not in result:
                print(f"{slug}: {result['paragraphs']} paragraphs loaded, no completed extraction run found")
            else:
                print(
                    f"{slug}: {result['paragraphs']} paragraphs, run={result['run_dir']}, "
                    f"+{result['Event']} events, +{result['Proposal']} proposals, "
                    f"+{result['ValuationAnalysis']} valuations (new rows this load)"
                )

        print("\n=== Row counts ===")
        for table, n in report_counts(conn).items():
            print(f"{table}: {n}")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
