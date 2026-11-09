"""Run the full DealTrace pipeline for one deal end to end.

    python -m src.run splunk
    python -m src.run splunk --model gemini-3.6-flash

fetch -> sections -> extract -> validate, for the one deal in DEALS.
"""

import argparse
import os

from dotenv import load_dotenv

from src import extract, fetch, sections, validate
from src.extract import Usage
from src.schemas import BackgroundExtraction, ValuationExtraction

load_dotenv()

DEALS = {
    "splunk": {
        "search_term": "splunk",
        "deal_name": "Cisco's Acquisition of Splunk",
        # Advisor/counsel/board names the model may use in place of the
        # company they represent -- gold rolls these up to the company;
        # see validate.normalize_party_roles.
        "party_map": {
            "Qatalyst": "Splunk",
            "Morgan Stanley": "Splunk",
            "Skadden": "Splunk",
            "Board": "Splunk",
            "Tidal Partners": "Cisco",
            "Simpson Thacher": "Cisco",
        },
    },
    "zendesk": {
        "search_term": "zendesk",
        "deal_name": "Hellman & Friedman and Permira's Acquisition of Zendesk",
        "party_map": {
            "Qatalyst": "Zendesk",
            "Goldman Sachs": "Zendesk",
            "Wachtell Lipton": "Zendesk",
            "Board": "Zendesk",
            "Fried Frank": "Consortium",
        },
        # Zendesk's own filing HTML mistags this sub-subsection at the same
        # heading depth as "Opinion of Goldman Sachs & Co. LLC" instead of
        # one level deeper like its siblings ("Selected Public Company
        # Comparables", "General"), so sections.py's general
        # OPINION_SUBSECTION_RE pattern doesn't recognize it as a
        # continuation and the section stops one subsection early. A
        # one-off quirk of this filing, not a general pattern -- see
        # sections.extract_sections' extra_continue_headings.
        "section_boundary_overrides": ["EV/NTM Revenue Multiple Over Time"],
    },
}

# Which container schema to run against which sections. Background of the
# Merger is where the negotiation timeline and price proposals live; the
# per-advisor opinion sections are where valuation multiples live.
# Management Projections is kept for context but has no schema of its own.
SECTION_SCHEMAS: dict[str, type] = {
    "background_of_the_merger": BackgroundExtraction,
}
OPINION_SCHEMA = ValuationExtraction

# Background of the Merger is long and paragraph-dense (first_contact
# through signing); splitting it into a few smaller calls on paragraph
# boundaries keeps each call's scope narrow enough for the model to work
# through it paragraph by paragraph instead of skimming a single huge one.
SECTION_TARGET_CHUNKS: dict[str, int] = {
    "background_of_the_merger": 3,
}


def run(deal_slug: str, model: str | None = None) -> None:
    if deal_slug not in DEALS:
        raise SystemExit(f"Unknown deal '{deal_slug}'. Known deals: {list(DEALS)}")
    deal = DEALS[deal_slug]
    resolved_model = model or os.environ["GEMINI_MODEL"]

    print(f"=== Step 1: fetch ({deal['deal_name']}) ===")
    fetch_result = fetch.fetch_defm14a(deal["search_term"])
    print(f"{fetch_result.company} DEFM14A filed {fetch_result.filing_date} ({fetch_result.accession_number})")
    print(f"From cache: {fetch_result.from_cache}\n")

    print("=== Step 2: sections ===")
    section_dict = sections.run(
        fetch_result.html_path, deal_slug, deal.get("section_boundary_overrides")
    )
    print()

    print(f"=== Step 3: extract (model={resolved_model}) ===")
    used, remaining = extract.quota_status(resolved_model)
    print(f"[quota] {resolved_model}: {used}/{extract.FREE_TIER_DAILY_QUOTA} used today, {remaining} remaining (local estimate)\n")

    records_by_type: dict[str, list] = {"Event": [], "Proposal": [], "ValuationAnalysis": []}
    total_usage = Usage()

    for section_key, section in section_dict.items():
        if section_key in SECTION_SCHEMAS:
            schema = SECTION_SCHEMAS[section_key]
        elif section_key.startswith("opinion_of_"):
            schema = OPINION_SCHEMA
        else:
            continue

        print(f"-- {section_key} ({len(section['paragraphs'])} paragraphs, schema={schema.__name__})")
        target_chunks = SECTION_TARGET_CHUNKS.get(section_key)
        instance, usage = extract.extract_section(
            section["paragraphs"], schema, model=model, target_chunks=target_chunks
        )
        if hasattr(instance, "events"):
            records_by_type["Event"].extend(instance.events)
        if hasattr(instance, "proposals"):
            records_by_type["Proposal"].extend(instance.proposals)
        if hasattr(instance, "valuation_analyses"):
            records_by_type["ValuationAnalysis"].extend(instance.valuation_analyses)
        total_usage.add(usage)

    print(
        f"\nExtraction totals: {len(records_by_type['Event'])} events, "
        f"{len(records_by_type['Proposal'])} proposals, "
        f"{len(records_by_type['ValuationAnalysis'])} valuation analyses"
    )
    print(
        f"Tokens used: prompt={total_usage.prompt_tokens}, output={total_usage.output_tokens}, "
        f"total={total_usage.total_tokens} ({total_usage.calls} live calls, {total_usage.cache_hits} cache hits)"
    )
    used, remaining = extract.quota_status(resolved_model)
    print(f"[quota] {resolved_model}: {used}/{extract.FREE_TIER_DAILY_QUOTA} used today, {remaining} remaining (local estimate)\n")

    print("=== Step 4: validate ===")
    results, extraction_path, summary_path = validate.run(
        records_by_type,
        deal["deal_name"],
        deal_slug,
        model=resolved_model,
        prompt_version=extract.PROMPT_VERSION,
        party_map=deal.get("party_map"),
    )
    n_pass = sum(1 for r in results if r["passed"])
    print(f"Validation: {n_pass}/{len(results)} records passed")
    print(f"Wrote {extraction_path}")
    print(f"Wrote {summary_path}")
    print(f"Latest run: {validate.LATEST_LINK}")

    print("\n=== DONE ===")
    print(f"Total tokens used this run: {total_usage.total_tokens}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the DealTrace pipeline for one deal.")
    parser.add_argument("deal_slug", help="Deal identifier, e.g. 'splunk'")
    parser.add_argument(
        "--model", default=None, help="Override GEMINI_MODEL from .env for this run"
    )
    args = parser.parse_args()
    run(args.deal_slug, model=args.model)


if __name__ == "__main__":
    main()
