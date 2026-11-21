# DealTrace

DealTrace reads SEC merger-proxy filings (DEFM14A, PREM14A, SC 14D9, SC
TO-T, S-4) and turns each one's "Background of the Merger" narrative
into a structured, sourced timeline: who was contacted, when, what was
proposed, how the price moved, and when it was signed — with every
fact traced back to the exact sentence in the filing that supports it.

It is not a general M&A database. It covers only deals whose filing
includes a background-of-the-merger-style narrative, and the dataset
described below is the current state of an actively-run pipeline, not
a finished, audited corpus. See **What this covers — and doesn't**
below before treating any number here as authoritative.

## Headline numbers

Pulled from the `headline_stats` table (`src/write_headline_stats.py`),
computed over the 823 target-side sale processes `deal_metrics` marks
included in cross-deal stats -- 1,125 deals total; 161 are duplicates
of another filing for the same underlying transaction (excluded by
`is_canonical`, leaving 964 canonical deals), and a further 141 of
those 964 are spin-offs, affiliated-manager mergers, holding-company
reorganizations, or buyer-side filings that `src/classify_deal_type.py`
excludes as not a genuine arm's-length sale process:

| Stat | n | p25 | median | p75 |
|---|---|---|---|---|
| Parties contacted per deal | 823 | 5 | 8 | 12 |
| Proposals per deal | 807 | 5 | 7 | 11 |
| Bidders who submitted a proposal | 807 | 1 | 2 | 4 |
| Days, first proposal → signing | 795 | 69 | 129 | 262.5 |
| First bidder is the eventual acquirer | 792 | — | 51.3% | — |
| Price increase, cash deals only | 346 | 0.5% | 9.7% | 23.5% |

`n` is smaller than 823 for stats that need a record not every deal
has. 16 of the 823 are a genuine sale process whose extraction
produced zero Proposal records at all (Twitter/Musk, New Relic) --
`deal_metrics.data_quality_flag = 'proposals_not_extracted'`, excluded
from the proposals/bidders/price-bump rows above only, never from the
site or from parties-contacted. The rest need a dated first-contact or
a cash-only final price that not every extraction run captured — see
`config/prompt_lock.json` and each stat's own `exclusions` column in
`headline_stats` for what was dropped and why. These figures aren't
regenerated automatically on every pipeline change -- re-run
`python -m src.write_headline_stats` and re-paste the table here (the
website itself always reads live from the database; only this README
snapshot needs a manual refresh).

**Accuracy was audited in three rounds of 20 randomly sampled deals,
each checked field-by-field against the source filing by an
independent model (Claude) with all flagged fields reviewed by the
author. Rounds 1–2 found systematic errors (buyer-side filings
mislabeled as sales, inflated bidder counts, wrong first-contact
dates), fixed with deterministic rules. Round 3, on a fresh sample: 18
of 20 deals were genuine target-side sale processes; across those, 81
of 90 extracted fields were correct or materially correct, 9 were
wrong — most often first-contact dates, which are therefore excluded
from headline statistics. Known limitations: some acquirers remain
unresolved ('Undisclosed'), and stock-for-stock deals have no
per-share cash price.**

## Pipeline

```
EDGAR discovery  →  classify  →  section split  →  Gemini extraction  →  quote validation  →  dedup / entity resolution  →  deal_metrics  →  Next.js
```

1. **Discover** (`src/discover.py`) — scans EDGAR's quarterly `form.idx`
   files for the five filing types above, groups them into candidate
   deals by target CIK, and records them in `deal_candidates`.
2. **Classify** (`src/classify.py`) — a no-LLM pass on SIC code and
   document text that separates real operating-company M&A from
   SPAC/de-SPAC mechanics and other non-M&A filings.
3. **Section split** (`src/sections.py`) — isolates the "Background of
   the Merger" narrative and fairness-opinion sections, paragraph by
   paragraph, so every later fact can cite a specific paragraph id.
4. **Gemini extraction** (`src/extract.py`) — `gemini-3.6-flash` via
   Vertex AI reads the isolated sections and returns structured
   `Event`, `Proposal`, and `ValuationAnalysis` records — never free
   text. This model retires January 28, 2027; raw outputs are archived
   (`data/cache`, `data/output/runs`, `data/output/bulk_runs`) since
   they can't be regenerated after that date.
5. **Quote validation** (`src/validate.py`) — every record's
   `source_quotes` must appear verbatim (after normalizing quote marks,
   dashes, and whitespace) in the paragraph it cites, every number it
   reports must appear in one of those quotes, and dates are resolved
   by code, never by the model.
6. **Dedup / entity resolution** (`src/dedup_deals.py`,
   `src/entity_match.py`, `src/filing_party_names.py`) — groups
   same-transaction filings into one canonical deal, and resolves
   acquirer/target names from the merger agreement's own party
   definitions rather than trusting the model's phrasing.
7. **`deal_metrics`** (`src/deal_metrics.py`) — the single source of
   truth for every number the site shows: one row per deal, with the
   acquirer/signing date/final price/bidder counts recomputed from
   that deal's one authoritative extraction run, plus
   `headline_stats` (`src/write_headline_stats.py`) for the
   cross-deal aggregates above.
8. **Next.js** (`apps/web`) — reads `deal_metrics`/`headline_stats`
   (and the underlying `events`/`proposals`/`valuations` for the
   per-deal evidence drawer) directly from Postgres; nothing is
   precomputed into static JSON.

## What this covers — and doesn't

**Covers:**
- Public-company sale processes where the filing carries a
  background-of-the-merger-style narrative.
- Every extracted fact quote-validated against its own filing before
  it's loaded (see pipeline step 5) — a fabricated or misquoted fact
  gets caught here.
- Full provenance: every fact links to the paragraph(s) and literal
  quote(s) it was extracted from, visible in the per-deal evidence
  drawer on the site.

**Doesn't cover:**
- SPAC/de-SPAC business combinations — classified and dropped before
  extraction; they don't have a comparable sale-process narrative.
- Filings whose background section a parser can't reliably isolate
  (logged, not silently skipped, but not in the dataset either).
- A correctly-quoted misreading of an ambiguous sentence —
  quote-matching confirms a quote is real, not that the model read it
  correctly. Human review of the bulk-extracted set is still in
  progress (see the spot-check placeholder above).
- The full timeline when a background section omits an early contact
  or proposal — "days to signing," "bidders," and the first-to-final
  price bump are derived only from what a given run actually
  extracted, so these understate the real process, not just the
  recorded one.
- Perfect de-duplication — automated discovery and classification are
  best-effort; the same underlying transaction can briefly surface as
  two separately tracked deals before de-duplication catches up.

## Stack

- **Pipeline**: Python 3.13, `google-genai` (Vertex AI / Gemini),
  `psycopg` for Postgres, `pydantic` for schema validation,
  `beautifulsoup4`/`lxml` for HTML section parsing. See
  `requirements.txt`.
- **Database**: Postgres (local for development; Supabase in
  production), schema-migrated via `db/migrate.py` and the SQL files
  in `db/migrations/`.
- **Web**: Next.js 16 (App Router, Turbopack) in `apps/web`, reading
  Postgres directly via `pg` — no separate API layer, no static
  generation of deal data.

## Running it locally

Requires Python 3.13+, Node 20+, a local Postgres instance, and a
Vertex AI-enabled GCP project (only needed if you're running new
extractions — reading the already-loaded data doesn't need it).

```bash
# 1. Python environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Secrets (never commit this file)
cp .env.example .env            # fill in DATABASE_URL
gcloud auth application-default login   # only needed to run new extractions (Vertex AI)

# 3. Schema
python -m db.migrate

# 4. Run the pipeline for one curated deal end to end
python -m src.run splunk

# 5. Load its output into Postgres
python -m src.load_db splunk

# 6. Recompute deal_metrics and headline_stats (one command writes both)
python -m src.deal_metrics

# 7. Web app
cd apps/web
cp .env.example .env   # or point DATABASE_URL at the same Postgres instance
npm install
npm run dev
```

Automated discovery of new deals (`python -m src.discover`) and the
bulk extraction pipeline (`src/bulk_run.py`, `src/load_bulk.py`) are
separate, longer-running entrypoints — see each module's own docstring
before running them; several call a billed LLM API.
