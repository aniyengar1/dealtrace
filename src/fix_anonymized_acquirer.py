"""Finds canonical bulk deals whose stored acquirer is itself an
anonymized placeholder ("Company A", "Party B", "Bidder 1") -- never a
valid acquirer, per src.entity_match.is_anonymized_placeholder -- and
fixes them using the named counterparty from the deal's own signing
event (src.bulk_quality_check.guess_acquirer, now signing-event-aware
and placeholder-excluding). A deal with no resolvable real name either
way is set to acquirer="Unknown" (an explicit unresolved marker, never
left on a placeholder).

    python -m src.fix_anonymized_acquirer

This also reruns the fix for every canonical bulk deal (not just ones
previously touched by src.fix_acquirer_acronyms), since the rule itself
-- a placeholder can never be the acquirer -- is new.
"""

import json
from pathlib import Path

from src.bulk_quality_check import guess_acquirer
from src.entity_match import is_anonymized_placeholder
from src.env import load_env
from src.load_bulk import bulk_slug
from src.load_db import connect

load_env()


def main() -> None:
    reports = json.loads(Path("data/output/bulk_quality_report.json").read_text())
    data_by_slug = {}
    for r in reports:
        slug = bulk_slug(r["row"]["target_cik"], r["row"]["primary_accession"])
        result = json.loads(Path(r["result_path"]).read_text())
        data_by_slug[slug] = (r["row"]["target_name"], result["proposals"], result["events"])

    found = []
    fixed = []
    marked_unresolved = []

    with connect() as conn:
        deals = conn.execute(
            "SELECT id, slug, target, acquirer FROM deals WHERE is_canonical AND slug LIKE 'bulk_%'"
        ).fetchall()

        for deal_id, slug, target, old_acquirer in deals:
            if not is_anonymized_placeholder(old_acquirer):
                continue
            found.append({"slug": slug, "target": target, "old_acquirer": old_acquirer})

            if slug not in data_by_slug:
                marked_unresolved.append({"slug": slug, "target": target, "old_acquirer": old_acquirer, "reason": "no cached data to re-derive from"})
                continue
            target_name, proposals, events = data_by_slug[slug]
            new_guess = guess_acquirer(target_name, proposals, events)

            if new_guess is None or is_anonymized_placeholder(new_guess):
                conn.execute(
                    "UPDATE deals SET acquirer = 'Unknown', deal_name = %s WHERE id = %s",
                    (f"Acquisition of {target} (acquirer unresolved)", deal_id),
                )
                marked_unresolved.append({"slug": slug, "target": target, "old_acquirer": old_acquirer, "best_guess": new_guess})
                continue

            new_deal_name = f"{new_guess}'s Acquisition of {target}"
            conn.execute(
                "UPDATE deals SET acquirer = %s, deal_name = %s WHERE id = %s",
                (new_guess, new_deal_name, deal_id),
            )
            fixed.append({"slug": slug, "target": target, "old_acquirer": old_acquirer, "new_acquirer": new_guess})

        conn.commit()

    print(json.dumps({
        "n_found": len(found),
        "n_fixed": len(fixed),
        "n_marked_unresolved": len(marked_unresolved),
        "fixed": fixed,
        "marked_unresolved": marked_unresolved,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
