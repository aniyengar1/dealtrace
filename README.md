# DealTrace

DealTrace reads SEC merger-proxy filings and turns each one's
"Background of the Merger" narrative into a structured, sourced
timeline — who was contacted, how the price moved, how long it took —
with every fact traced back to the exact sentence that supports it. A
second, independent project in the same app, Crosscheck, locks
quarterly revenue probability predictions before each company's
earnings release and scores them against the real result once it's
public.

**Live:** [dealtrace-research.vercel.app](https://dealtrace-research.vercel.app)

## Headline findings

Pulled from the current `data/output/stats/headline_stats.json`:

- **Most sale processes aren't crowded.** Median **2** distinct bidders
  per deal (n = 758) — real competitive auctions with several serious
  bidders are the exception, not the rule.
- **In a real contest, showing up first is an edge, not a guarantee.**
  Restricted to deals with 2+ bidders, the first bidder to submit a
  priced proposal goes on to win **40%** of the time (n = 485). Across
  *all* deals the figure reads higher, 61% (n = 747), only because a
  1-bidder deal wins by definition.
- **Competition still moves the price.** For deals that end in cash,
  the median increase from the first priced bid to the signed price is
  **9.7%** (n = 344).

The full distribution (p25/median/p75) for these and three other
stats — parties contacted, proposals per deal, days from first
proposal to signing — is on the site's [/stats](https://dealtrace-research.vercel.app/stats)
page, always read live from Postgres, never a static snapshot.

## How it works

```
EDGAR filings  →  LLM extraction  →  quote validation  →  Postgres  →  Next.js (Supabase + Vercel)
```

1. **Discover & classify** — EDGAR's own filing index is scanned for
   merger-proxy and tender-offer filings (DEFM14A, PREM14A, SC 14D9, SC
   TO-T, S-4); a no-LLM pass separates real M&A from SPAC mechanics and
   other non-deal filings.
2. **Extract** — an LLM reads the isolated "Background of the Merger"
   narrative and returns structured records (who proposed what, when,
   at what price) — never free text.
3. **Validate** — every extracted fact's quote must appear verbatim in
   the filing paragraph it cites, and every number it reports must
   appear in that quote. Dates are resolved by code, never the model.
4. **Load** — validated records land in Postgres, deduplicated across
   filings for the same underlying transaction, with acquirer/target
   names resolved from the merger agreement's own party definitions.
5. **Serve** — a Next.js app reads Postgres directly (no static
   generation of deal data), deployed on Vercel against a Supabase
   Postgres instance.

## Accuracy & limitations

Accuracy was audited in three rounds of 20 randomly sampled deals,
each checked field-by-field against the source filing by an
independent model with every flagged field reviewed by hand. The first
two rounds found systematic errors (buyer-side filings mislabeled as
sales, inflated bidder counts, wrong first-contact dates) and each was
fixed with a deterministic rule, not a one-off patch. The third round,
on a fresh sample: 18 of 20 deals were genuine target-side sale
processes, and across those, 81 of 90 extracted fields were correct or
materially correct — the 9 that weren't were mostly first-contact
dates, which is why that field is excluded from the headline stats
above.

Known, honestly-scoped limits: some acquirers remain unresolved
("Undisclosed") rather than guessed; a stock-for-stock deal has no
single per-share cash price; "days to signing" and bidder counts
reflect only what a given extraction run actually found, so they can
understate — never fabricate — the real process; and human review of
the full bulk-extracted set is still in progress. This is not a
general M&A database — it covers only deals whose filing carries a
background-of-the-merger-style narrative — and the numbers above
describe an actively-run pipeline, not a finished, audited corpus.

## Crosscheck: pre-registered earnings predictions

A separate section of the site, [/crosscheck/predictions](https://dealtrace-research.vercel.app/crosscheck/predictions),
answers a narrower, falsifiable question: will a company's reported
quarterly revenue land below, within, or above its own management
guidance range? Each prediction is **locked before the company's
earnings release** — timestamped and hash-sealed against the evidence
it was made from — not fit after the fact. The underlying ledger is
append-only: a correction is a new, separately versioned record, never
an edit to what was already locked. Several of the companies in the
current locked batch report in **December 2026**; this project doesn't
score a prediction until the real result is public, and the public
page reads a separate, published-only copy of the ledger rather than
the live one.

A retrospective walk-forward backtest is published alongside the live
predictions, clearly labeled as a retrospective reconstruction, not a
live track record — its own reported confidence interval includes
zero, and the page says so rather than rounding that away.

## Stack

- **Pipeline**: Python 3.13, `google-genai` (Vertex AI / Gemini),
  `psycopg` for Postgres, `pydantic` for schema validation,
  `beautifulsoup4`/`lxml` for HTML parsing.
- **Database**: Postgres — local for development, [Supabase](https://supabase.com)
  in production — schema-migrated via versioned SQL files.
- **Web**: [Next.js](https://nextjs.org) 16 (App Router, Turbopack),
  reading Postgres directly via `pg`, deployed on [Vercel](https://vercel.com).

## Running it locally

Requires Python 3.13+, Node 20+, a local Postgres instance, and (only
if you're running new extractions, not reading already-loaded data) a
Vertex AI-enabled GCP project.

```bash
# 1. Python environment
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Secrets (copy the template, then fill in your own values -- never commit the result)
cp .env.example .env
gcloud auth application-default login   # only needed to run new extractions

# 3. Schema
python -m db.migrate

# 4. Run the pipeline for one curated deal end to end
python -m src.run splunk
python -m src.load_db splunk

# 5. Recompute deal_metrics and headline_stats
python -m src.deal_metrics

# 6. Web app
cd apps/web
cp .env.example .env   # or point DATABASE_URL at the same local Postgres instance
npm install
npm run dev
```

Automated discovery (`python -m src.discover`) and the bulk extraction
pipeline (`src/bulk_run.py`, `src/load_bulk.py`) are separate,
longer-running entrypoints that call a billed LLM API — see each
module's own docstring before running them.
