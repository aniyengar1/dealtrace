"""Run the full DealTrace pipeline for one deal end to end.

    python -m src.run splunk
    python -m src.run splunk --model gemini-3.6-flash

fetch -> sections -> extract -> validate, for the one deal in DEALS.
"""

import argparse
import os

from dotenv import load_dotenv

from src import extract, fetch, sanity, sections, validate
from src.extract import Usage
from src.schemas import BackgroundExtraction, ValuationExtraction

load_dotenv()

DEALS = {
    "splunk": {
        "search_term": "splunk",
        "deal_name": "Cisco's Acquisition of Splunk",
        "target": "Splunk",
        "acquirer": "Cisco",
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
        "target": "Zendesk",
        "acquirer": "Consortium",
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
    "cvent": {
        "search_term": "cvent holding corp",
        "deal_name": "Blackstone's Acquisition of Cvent",
        "target": "Cvent",
        "acquirer": "Blackstone",
        # No party_map yet -- build one from the actual extraction once
        # this deal is run, the way Splunk's and Zendesk's were.
    },
    # The 7 deals below all use a filing-agent template with no semantic
    # h1-h5 heading markup at all, unlike the 3 above -- sections.py's
    # fallback parser (candidate headings from styling/known chapter
    # names, not heading depth) handles them. All verified to section
    # cleanly: every background_of_the_merger stops at a real, checked
    # "Recommendation of the Board..."-style heading. No party_map yet for
    # any of them -- same as Cvent, build one from a real extraction.
    "anaplan": {
        "search_term": "anaplan",
        "deal_name": "Thoma Bravo's Acquisition of Anaplan",
        "target": "Anaplan",
        "acquirer": "Thoma Bravo",
    },
    "citrix": {
        "search_term": "citrix systems",
        "deal_name": "Vista Equity Partners and Evergreen Coast Capital's Acquisition of Citrix",
        "target": "Citrix",
        "acquirer": "Vista",
    },
    "coupa": {
        "search_term": "coupa software",
        "deal_name": "Thoma Bravo's Acquisition of Coupa",
        "target": "Coupa",
        "acquirer": "Thoma Bravo",
    },
    "new_relic": {
        "search_term": "new relic",
        "deal_name": "Francisco Partners and TPG's Acquisition of New Relic",
        "target": "New Relic",
        "acquirer": "Francisco Partners",
    },
    "mandiant": {
        "search_term": "mandiant",
        "deal_name": "Google's Acquisition of Mandiant",
        "target": "Mandiant",
        "acquirer": "Google",
    },
    "activision": {
        "search_term": "activision blizzard",
        "deal_name": "Microsoft's Acquisition of Activision Blizzard",
        "target": "Activision Blizzard",
        "acquirer": "Microsoft",
    },
    "twitter": {
        "search_term": "twitter",
        "deal_name": "Elon Musk's Acquisition of Twitter",
        "target": "Twitter",
        "acquirer": "Musk",
        # background_of_the_merger is genuinely ~23,500 words (verified
        # the end boundary -- it's not a bug, the litigation made this an
        # unusually long chronology). Will likely need more target_chunks
        # than the other deals' default when this is actually extracted.
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

    print("\n=== Step 5: deal-level sanity checks ===")
    validated_by_type: dict[str, list] = {"Event": [], "Proposal": [], "ValuationAnalysis": []}
    for r in results:
        validated_by_type[r["record_type"]].append(r["record"])
    html = fetch_result.html_path.read_text(encoding="utf-8", errors="replace")
    sanity_results = sanity.run(validated_by_type, html, deal.get("target", ""), deal.get("acquirer", ""))
    print(sanity.format_report(deal["deal_name"], sanity_results))

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
