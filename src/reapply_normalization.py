"""Re-apply validate.py's normalization functions to already-loaded deals,
without calling the LLM again.

    python -m src.reapply_normalization            # all deals with a loaded run
    python -m src.reapply_normalization cvent       # just one

For each deal's latest run folder, re-reads <slug>_extraction.json, re-runs
normalize_defined_terms/normalize_party_roles on every record (idempotent --
already-resolved values pass straight through), and for any record whose
parties/proposer/recipient changed: updates the DB row (matched by the
record's PRE-change content_hash, which is what's currently stored) and
rewrites extraction.json on disk with the new values. Both the DB row's
content_hash and the on-disk content_hash are updated together so the
(run_id, content_hash) row stays the live identity key for the record's
current fields -- re-running this script (or a plain load_db reload)
afterwards is a no-op, same as any other idempotent load.
"""

import json
import sys

import psycopg
from dotenv import load_dotenv

from src import fetch, sanity
from src.load_db import DATA_RUNS, connect, content_hash
from src.run import DEALS
from src.validate import normalize_defined_terms, normalize_party_roles

load_dotenv()


def _find_loaded_run(conn: psycopg.Connection, slug: str) -> tuple[str, str] | None:
    """The run this deal actually has loaded in the DB (most recently
    loaded, by extraction_runs.started_at) -- NOT necessarily the latest
    run folder on disk, which may be a newer run nobody's loaded yet.
    Returns (run_id, run_dir_name) or None if this deal has no loaded run."""
    row = conn.execute(
        """
        SELECT r.id, r.run_dir FROM extraction_runs r
        JOIN deals d ON d.id = r.deal_id
        WHERE d.slug = %s
        ORDER BY r.started_at DESC
        LIMIT 1
        """,
        (slug,),
    ).fetchone()
    return (row[0], row[1]) if row else None


_TABLE_BY_RECORD_TYPE = {
    "Event": ("events", None),
    "Proposal": ("proposals", ("proposer", "recipient")),
    "ValuationAnalysis": ("valuations", None),
}


def _normalize_results(results: list[dict], deal: dict) -> list[dict]:
    """Group an extraction.json's flat result list by record_type, re-run
    the two normalize_* passes (same order as validate.run), then flatten
    back -- preserving each result's passed/failure_reasons untouched."""
    records_by_type: dict[str, list] = {"Event": [], "Proposal": [], "ValuationAnalysis": []}
    for r in results:
        records_by_type[r["record_type"]].append(r["record"])

    target_name, acquirer_name = deal.get("target"), deal.get("acquirer")
    if target_name and acquirer_name:
        records_by_type = normalize_defined_terms(records_by_type, target_name, acquirer_name)
    party_map = deal.get("party_map")
    if party_map:
        records_by_type = normalize_party_roles(records_by_type, party_map)

    cursors = {k: iter(v) for k, v in records_by_type.items()}
    return [{**r, "record": next(cursors[r["record_type"]])} for r in results]


def reapply_deal(conn: psycopg.Connection, slug: str) -> dict:
    """Returns {slug, run_dir, updated: {Event: n, Proposal: n, ValuationAnalysis: n}}
    or {slug, run_dir: None} if this deal has no loaded run."""
    deal = DEALS[slug]
    loaded = _find_loaded_run(conn, slug)
    if loaded is None:
        return {"slug": slug, "run_dir": None}
    run_id, run_dir_name = loaded

    extraction_path = DATA_RUNS / run_dir_name / f"{slug}_extraction.json"
    old_results = json.loads(extraction_path.read_text())
    new_results = _normalize_results(old_results, deal)

    updated = {"Event": 0, "Proposal": 0, "ValuationAnalysis": 0}
    for old_r, new_r in zip(old_results, new_results):
        old_hash = content_hash(old_r["record"])
        new_hash = content_hash(new_r["record"])
        if old_hash == new_hash:
            continue
        table, proposer_recipient_cols = _TABLE_BY_RECORD_TYPE[old_r["record_type"]]
        if proposer_recipient_cols:
            conn.execute(
                f"UPDATE {table} SET proposer = %s, recipient = %s, content_hash = %s "
                f"WHERE run_id = %s AND content_hash = %s",
                (
                    new_r["record"]["proposer"],
                    new_r["record"]["recipient"],
                    new_hash,
                    run_id,
                    old_hash,
                ),
            )
        else:
            conn.execute(
                f"UPDATE {table} SET parties = %s, content_hash = %s "
                f"WHERE run_id = %s AND content_hash = %s",
                (new_r["record"].get("parties", []), new_hash, run_id, old_hash),
            )
        updated[old_r["record_type"]] += 1

    extraction_path.write_text(json.dumps(new_results, indent=2, default=str))
    return {"slug": slug, "run_dir": run_dir_name, "updated": updated}


def sanity_recheck(conn: psycopg.Connection, slug: str) -> list[dict]:
    """Re-runs sanity.run() against the just-updated extraction.json on disk."""
    deal = DEALS[slug]
    run_id, run_dir_name = _find_loaded_run(conn, slug)
    results = json.loads((DATA_RUNS / run_dir_name / f"{slug}_extraction.json").read_text())
    records_by_type: dict[str, list] = {"Event": [], "Proposal": [], "ValuationAnalysis": []}
    for r in results:
        records_by_type[r["record_type"]].append(r["record"])
    fetch_result = fetch.fetch_defm14a(deal["search_term"])
    html = fetch_result.html_path.read_text(encoding="utf-8", errors="replace")
    return sanity.run(records_by_type, html, deal.get("target", ""), deal.get("acquirer", ""))


def main(slugs: list[str] | None = None) -> None:
    slugs = slugs or list(DEALS)
    with connect() as conn:
        for slug in slugs:
            result = reapply_deal(conn, slug)
            conn.commit()
            if result["run_dir"] is None:
                print(f"{slug}: no loaded run, skipped")
                continue
            u = result["updated"]
            print(
                f"{slug} ({result['run_dir']}): {u['Event']} event(s), "
                f"{u['Proposal']} proposal(s), {u['ValuationAnalysis']} valuation(s) updated"
            )
            sanity_results = sanity_recheck(conn, slug)
            print(sanity.format_report(DEALS[slug]["deal_name"], sanity_results))
            print()


if __name__ == "__main__":
    main(sys.argv[1:] or None)
