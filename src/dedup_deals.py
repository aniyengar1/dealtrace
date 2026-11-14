"""Marks duplicate deals.rows for the same real-world transaction --
e.g. a curated deal and its separately-bulk-discovered counterpart
(the "two Splunk rows" case), or a merger's two sides each filing their
own primary document (target's DEFM14A vs. acquirer's registrant S-4,
as with Knoll/Herman Miller) -- without deleting anything.

    python -m src.dedup_deals

Two deals are clustered as the same transaction only when they share an
EXACT latest-signing-date match (a real anchor, not a guess) AND their
(target, acquirer) name pairs share at least one company identity via
src.entity_match.is_same_entity -- both conditions required, so a
company that was acquired twice in different eras, or a serial acquirer
like Diamondback appearing as registrant on 3 unrelated S-4s, can't
collide (different signing dates). Deals with no resolvable signing
date are left untouched -- not deduped, but also not risked.

Within a cluster, the canonical row is chosen by tier: curated (not
bulk-discovered) > DEFM14A > an amendment ("/A" suffix form) > anything
else; ties broken by the most recently filed. Every other member in
the cluster gets is_canonical=false and duplicate_of=<canonical id>.
"""

import json
from collections import defaultdict

import psycopg

from src.entity_match import core_name, is_same_entity
from src.env import load_env
from src.load_db import connect

load_env()

# acquirer_guess falls back to one of these generic placeholders when the
# extracted text never named a real acquirer (unresolved "Parent"/"Merger
# Sub" terms, or an unnamed sponsor group). Two unrelated deals that both
# happen to have, say, acquirer="Parent" are NOT the same transaction --
# comparing a generic placeholder against another generic placeholder
# produced a real false-positive cluster (Dawson Geophysical / PAE Inc /
# Wilks Brothers, three unrelated deals that all guessed "Parent") before
# this exclusion existed.
_GENERIC_ACQUIRER_TERMS = {
    "unknown", "parent", "merger sub", "acquiror", "buyer", "consortium", "sponsor",
}


def _is_generic(name: str) -> bool:
    return core_name(name) in _GENERIC_ACQUIRER_TERMS


def _bulk_cik_accession(slug: str) -> tuple[str, str]:
    _, cik, accession_nodash = slug.split("_")
    return cik, f"{accession_nodash[:10]}-{accession_nodash[10:12]}-{accession_nodash[12:18]}"


def _fetch_deals(conn: psycopg.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT d.id, d.slug, d.target, d.acquirer,
               (SELECT max(e.date_start) FROM events e
                JOIN extraction_runs r ON r.id = e.run_id
                WHERE r.deal_id = d.id AND e.event_type = 'signing' AND e.passed) AS signing_date
        FROM deals d
        """
    ).fetchall()

    deals = []
    for deal_id, slug, target, acquirer, signing_date in rows:
        is_bulk = slug.startswith("bulk_")
        form_type = None
        filed_date = None
        if is_bulk:
            cik, accession = _bulk_cik_accession(slug)
            candidate = conn.execute(
                "SELECT primary_form_type, primary_filed_date FROM deal_candidates WHERE primary_accession = %s",
                (accession,),
            ).fetchone()
            if candidate:
                form_type, filed_date = candidate
        deals.append(
            {
                "id": deal_id,
                "slug": slug,
                "target": target,
                "acquirer": acquirer,
                "signing_date": signing_date,
                "is_bulk": is_bulk,
                "form_type": form_type,
                "filed_date": filed_date,
            }
        )
    return deals


def _tier(deal: dict) -> int:
    if not deal["is_bulk"]:
        return 0
    form = (deal["form_type"] or "").upper()
    if form == "DEFM14A":
        return 1
    if form.endswith("/A"):
        return 2
    return 3


def _canonical_sort_key(deal: dict):
    # Most-recent filed_date first within a tier; curated deals have no
    # filed_date (None sorts first under "smaller is better", so flip
    # sign via a date ordinal with a safe fallback of 0).
    filed_ordinal = deal["filed_date"].toordinal() if deal["filed_date"] else 0
    return (_tier(deal), -filed_ordinal)


def _same_transaction(a: dict, b: dict) -> bool:
    pairs = [
        (a["target"], b["target"]),
        (a["target"], b["acquirer"]),
        (a["acquirer"], b["target"]),
        (a["acquirer"], b["acquirer"]),
    ]
    return any(
        not _is_generic(x) and not _is_generic(y) and is_same_entity(x, y) for x, y in pairs
    )


def find_clusters(deals: list[dict]) -> list[list[dict]]:
    by_date = defaultdict(list)
    for d in deals:
        if d["signing_date"] is not None:
            by_date[d["signing_date"]].append(d)

    clusters = []
    for _, group in by_date.items():
        # Union-find over this date's deals by shared company identity.
        parent = {d["id"]: d["id"] for d in group}

        def find(x):
            while parent[x] != x:
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for i, a in enumerate(group):
            for b in group[i + 1 :]:
                if _same_transaction(a, b):
                    union(a["id"], b["id"])

        by_root = defaultdict(list)
        for d in group:
            by_root[find(d["id"])].append(d)
        clusters.extend(c for c in by_root.values() if len(c) > 1)

    return clusters


def apply_dedup(conn: psycopg.Connection, clusters: list[list[dict]]) -> dict:
    n_marked = 0
    causes = {"curated_vs_bulk": 0, "bulk_vs_bulk": 0}
    details = []
    for cluster in clusters:
        cluster_sorted = sorted(cluster, key=_canonical_sort_key)
        canonical = cluster_sorted[0]
        duplicates = cluster_sorted[1:]
        cause = "curated_vs_bulk" if any(not d["is_bulk"] for d in cluster) else "bulk_vs_bulk"
        causes[cause] += 1
        for dup in duplicates:
            conn.execute(
                "UPDATE deals SET is_canonical = false, duplicate_of = %s WHERE id = %s",
                (canonical["id"], dup["id"]),
            )
            n_marked += 1
        details.append(
            {
                "canonical": {"slug": canonical["slug"], "target": canonical["target"], "acquirer": canonical["acquirer"]},
                "duplicates": [{"slug": d["slug"], "target": d["target"], "acquirer": d["acquirer"]} for d in duplicates],
                "cause": cause,
            }
        )
    return {"n_groups": len(clusters), "n_marked_duplicate": n_marked, "by_cause": causes, "details": details}


def main() -> None:
    with connect() as conn:
        deals = _fetch_deals(conn)
        clusters = find_clusters(deals)
        result = apply_dedup(conn, clusters)
        conn.commit()
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
