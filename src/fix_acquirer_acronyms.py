"""Finds canonical deals whose stored acquirer is actually the target
-- an acronym/initials of the target's name ("USS" for "UNITED STATES
STEEL CORP"), or one of validate._TARGET_DEFINED_TERMS -- and attempts
to fix them by recomputing guess_acquirer with the now-acronym-aware
resolver (src.bulk_quality_check._resolve_target_placeholder). A fix
only lands when the recomputed guess is itself a real, non-target,
non-generic name; otherwise the deal is left as-is and counted
"unresolved" rather than overwritten with a worse guess.

    python -m src.fix_acquirer_acronyms

Curated deals are skipped (hand-curated, not bulk-extraction output);
only canonical bulk deals (is_canonical AND slug LIKE 'bulk_%') are
checked, since a non-canonical duplicate's acquirer field doesn't feed
any stat.
"""

import json
from pathlib import Path

from src.bulk_quality_check import guess_acquirer
from src.dedup_deals import _is_generic
from src.entity_match import is_acronym_of, is_same_entity
from src.env import load_env
from src.load_bulk import bulk_slug
from src.load_db import connect
from src import validate

load_env()


def _is_target_self_reference(acquirer: str, target: str) -> bool:
    if not acquirer:
        return False
    return (
        acquirer.strip().lower() in validate._TARGET_DEFINED_TERMS
        or is_same_entity(acquirer, target)
        or is_acronym_of(acquirer, target)
    )


def main() -> None:
    reports = json.loads(Path("data/output/bulk_quality_report.json").read_text())
    proposals_by_slug = {}
    for r in reports:
        slug = bulk_slug(r["row"]["target_cik"], r["row"]["primary_accession"])
        result = json.loads(Path(r["result_path"]).read_text())
        proposals_by_slug[slug] = (r["row"]["target_name"], result["proposals"], result["events"])

    found = []
    fixed = []
    unresolved = []

    with connect() as conn:
        deals = conn.execute(
            "SELECT id, slug, target, acquirer FROM deals WHERE is_canonical AND slug LIKE 'bulk_%'"
        ).fetchall()

        for deal_id, slug, target, old_acquirer in deals:
            if not _is_target_self_reference(old_acquirer, target):
                continue
            found.append({"slug": slug, "target": target, "old_acquirer": old_acquirer})

            if slug not in proposals_by_slug:
                unresolved.append({"slug": slug, "target": target, "old_acquirer": old_acquirer, "reason": "no cached proposals to re-derive from"})
                continue
            target_name, proposals, events = proposals_by_slug[slug]
            new_guess = guess_acquirer(target_name, proposals, events)

            is_still_self_or_generic = (
                new_guess is None
                or _is_target_self_reference(new_guess, target)
                or _is_generic(new_guess)
            )
            if is_still_self_or_generic:
                unresolved.append({"slug": slug, "target": target, "old_acquirer": old_acquirer, "best_guess": new_guess, "reason": "no better non-target, non-generic name found"})
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
        "n_unresolved": len(unresolved),
        "fixed": fixed,
        "unresolved": unresolved,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
