"""Loads bulk-discovered candidates (data/output/bulk_runs/*.json) into
Postgres, idempotently, using the pass/fail determination already made by
src.bulk_quality_report (data/output/bulk_quality_report.json: a deal
"passes" unless its quote_match_rate < QUOTE_MATCH_FAIL_THRESHOLD or it
has no extracted signing event).

    python -m src.load_bulk

Reuses load_db.py's generic, content-hash-keyed upsert_event/
upsert_proposal (re-running never duplicates rows) but NOT
upsert_deal/upsert_extraction_run's slug and run_dir conventions, which
are built around the hand-curated DEALS registry's
"<timestamp>_<slug>_<model>_<prompt_version>" folder-name format -- bulk
candidates have no such folder, so this module mints its own stable,
deterministic (never wall-clock-dependent, so reruns are idempotent)
slug and run_dir from the candidate's own CIK + accession number.

Deals that fail are NOT written to the deals table at all; they're
recorded with a reason in data/output/bulk_load_quarantine.json instead.
"""

import datetime
import json
from pathlib import Path

import psycopg

from src import validate
from src.bulk_quality_report import QUOTE_MATCH_FAIL_THRESHOLD, REPORT_PATH
from src.bulk_run import load_cached_html
from src.env import load_env
from src.load_db import connect, content_hash, report_counts, upsert_event, upsert_proposal
from src import sections as sections_module

load_env()

QUARANTINE_PATH = Path("data/output/bulk_load_quarantine.json")


def bulk_slug(target_cik: str, primary_accession: str) -> str:
    return f"bulk_{target_cik}_{primary_accession.replace('-', '')}"


def passes(report: dict) -> bool:
    qmr = report.get("quote_match_rate")
    return bool(report["has_signing_event"]) and qmr is not None and qmr >= QUOTE_MATCH_FAIL_THRESHOLD


def quarantine_reason(report: dict) -> str:
    qmr = report.get("quote_match_rate")
    if not report["has_signing_event"]:
        return "no extracted signing event"
    if qmr is None:
        return "no validatable records"
    return f"quote_match_rate {qmr:.1%} < {QUOTE_MATCH_FAIL_THRESHOLD:.0%} threshold"


def upsert_bulk_deal(conn: psycopg.Connection, slug: str, target_name: str, acquirer_guess: str | None) -> str:
    acquirer = acquirer_guess or "Unknown"
    deal_name = f"{acquirer}'s Acquisition of {target_name}" if acquirer_guess else f"Acquisition of {target_name}"
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
        (slug, deal_name, target_name, acquirer, target_name),
    ).fetchone()
    return row[0]


def upsert_bulk_extraction_run(
    conn: psycopg.Connection, deal_id: str, slug: str, model: str, started_at
) -> str:
    run_dir = f"bulk_{slug}_{model}"
    row = conn.execute(
        """
        INSERT INTO extraction_runs (deal_id, run_dir, model, prompt_version, started_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (run_dir) DO UPDATE SET
            model = EXCLUDED.model,
            started_at = EXCLUDED.started_at
        RETURNING id
        """,
        (deal_id, run_dir, model, "bulk-v1", started_at),
    ).fetchone()
    return row[0]


def load_one(conn: psycopg.Connection, report: dict) -> dict:
    row = report["row"]
    result_path = Path(report["result_path"])
    result = json.loads(result_path.read_text())

    slug = bulk_slug(row["target_cik"], row["primary_accession"])
    deal_id = upsert_bulk_deal(conn, slug, row["target_name"], report.get("acquirer_guess"))

    html = load_cached_html(row["target_cik"], row["primary_accession"])
    found = sections_module.extract_sections(html) if html else {}
    section = found.get("background_of_the_merger")
    paragraph_lookup = {p["id"]: p["text"] for p in section["paragraphs"]} if section else {}

    validated = validate.validate_all(
        {"Event": result["events"], "Proposal": result["proposals"]}, paragraph_lookup
    )

    started_at = datetime.datetime.fromtimestamp(result_path.stat().st_mtime, tz=datetime.timezone.utc)
    run_id = upsert_bulk_extraction_run(conn, deal_id, slug, result["model"], started_at)

    counts = {"Event": 0, "Proposal": 0}
    for r in validated:
        upsert = upsert_event if r["record_type"] == "Event" else upsert_proposal
        inserted = upsert(conn, run_id, r["record"], r["passed"], r["failure_reasons"])
        if inserted:
            counts[r["record_type"]] += 1

    return {"slug": slug, "target_name": row["target_name"], **counts}


def main() -> None:
    reports = json.loads(REPORT_PATH.read_text())

    loaded = []
    quarantined = []
    with connect() as conn:
        for report in reports:
            if passes(report):
                try:
                    result = load_one(conn, report)
                    conn.commit()
                    loaded.append(result)
                except psycopg.Error as exc:
                    # A record that quotes the filing correctly can still fail
                    # to fit the DB schema (e.g. an enterprise-value figure in
                    # a column sized for per-share prices) -- that's a load
                    # failure, not an extraction failure, but it still means
                    # this deal doesn't get loaded, so it's quarantined like
                    # any other failure rather than aborting the whole run.
                    conn.rollback()
                    quarantined.append(
                        {
                            "target_name": report["target_name"],
                            "target_cik": report["row"]["target_cik"],
                            "primary_accession": report["row"]["primary_accession"],
                            "quote_match_rate": report.get("quote_match_rate"),
                            "has_signing_event": report["has_signing_event"],
                            "reason": f"db load error: {exc}",
                        }
                    )
            else:
                quarantined.append(
                    {
                        "target_name": report["target_name"],
                        "target_cik": report["row"]["target_cik"],
                        "primary_accession": report["row"]["primary_accession"],
                        "quote_match_rate": report.get("quote_match_rate"),
                        "has_signing_event": report["has_signing_event"],
                        "reason": quarantine_reason(report),
                    }
                )

        QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        QUARANTINE_PATH.write_text(json.dumps(quarantined, indent=2))

        print(f"loaded: {len(loaded)}  quarantined: {len(quarantined)}")
        print("\n=== Row counts ===")
        for table, n in report_counts(conn).items():
            print(f"{table}: {n}")


if __name__ == "__main__":
    main()
