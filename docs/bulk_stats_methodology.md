# Bulk deal dataset: methodology and known limitations

Backing doc for `data/output/stats/headline_stats.json` (see
`src/write_headline_stats.py`) and any future methodology page that
surfaces it on the website.

## Scope

- EDGAR full-text scan, 2021-Q1 through present (~5.75 years), form
  types DEFM14A / PREM14A / SC 14D9 / SC TO-T / S-4.
- Classification restricted to `public_company_acquisition` (SPAC/de-SPAC
  and other non-operating-company transactions excluded; see
  `src/classify.py`).
- Extraction via `gemini-3.6-flash` (Vertex AI), default thinking,
  conservative pricing. 1,174 candidates processed; 1,115 passed
  validation and sanity thresholds and were loaded.

## Deduplication

A single real-world transaction can produce two independent rows in
this dataset: the target's own filing (DEFM14A/SC 14D9) and the
acquirer's registrant filing (S-4) for the same merger, or a curated
gold deal and its separately-bulk-discovered counterpart. `src.dedup_deals`
merges these: two deals are the same transaction only if they share an
**exact** latest-signing-date match **and** their (target, acquirer)
name pairs share a company identity (`src.entity_match.is_same_entity`,
which strips legal-entity suffixes so "Knoll" and "KNOLL INC" compare
equal). Generic placeholder acquirer names ("Parent", "Unknown",
"Consortium", etc.) are excluded from the identity comparison -- two
unrelated deals that both failed to resolve a real acquirer name must
not be allowed to collide on that alone (an earlier version of this
check did exactly that and wrongly merged three unrelated deals that
all guessed "Parent").

**Known gap:** a deal pair can only be merged if at least one side has
a resolvable signing date. Two of the ten curated deals (Twitter, New
Relic) have no loaded signing event, so their bulk-discovered
duplicates were NOT merged and remain as separate, non-canonical-vs-each-other
rows. This is a deliberate conservative tradeoff (missing a real
duplicate, rather than risking a false merge).

Of 1,125 total deals (10 curated + 1,115 bulk), **161 were marked
duplicates** (8 curated-vs-bulk, 153 bulk-vs-bulk), leaving 964
canonical deals. Non-canonical rows are never deleted --
`deals.is_canonical` / `deals.duplicate_of` record the decision.

## Acquirer-name heuristic

`acquirer` is a best-effort guess (`src.bulk_quality_check.guess_acquirer`):
the most common non-target name across a deal's proposals. It is not
authoritative. A systematic bug -- exact string matching missed almost
every informal short name against EDGAR's raw legal target name (e.g.
"Knoll" vs "KNOLL INC"), letting the target's own short name get
miscounted as a candidate acquirer -- was fixed this session and
affected **451 of 1,115** bulk deals' stored acquirer field (corrected
in place; see commit history). Some deals still show a generic
placeholder ("Parent", a conflicts-committee name) instead of a real
acquirer when no real name was ever the most frequent mention --
expected, not a bug, just a case where the heuristic has no better
answer.

## Signing-event extraction recall

Across all 1,174 processed candidates, ~95.6% have at least one
extracted `signing`-type event; the raw `signing_event_exists` sanity
check reports a much lower pass rate (~13%) but that check additionally
requires the raw EDGAR legal name to literally co-occur with the
guessed acquirer name in the event's `parties` text -- a much stricter,
name-formatting-sensitive bar not used for load/quarantine decisions.

A manual read of 5 of the 52 "no signing event" deals found the causes
are mixed: at least one genuinely has no signing moment in the filing
narrative (a unilateral tender offer with no negotiated merger
agreement), at least one is a clear section-finder truncation (the
background section captured was 6 paragraphs out of a much larger
document), and at least one is a clear extraction miss (the filing
explicitly narrates execution of the merger agreement but no `signing`
event was produced). The 95.6% recall figure should be read as a floor,
not a precise number -- some fraction of the 52 are recoverable misses,
not genuine absences.

## Data-quality exclusions in headline stats (`src.bulk_stats`)

- **% price increase (first proposal -> final)**: restricted to deals
  whose final proposal is cash and both prices are known; additionally
  excludes a first price under $0.10/share, a first price under 5% of
  the final price (catches a near-zero or unit-mismatched first price
  producing an absurd percentage, e.g. a $0.20 first price against a
  $6.6M final value), and any resulting `|% change| > 300%`. Every
  exclusion is listed by deal name and reason in the stats output, never
  silently dropped.
- **Days first-contact/first-proposal -> signing**: negative durations
  (signing before the deal's own start date -- almost certainly a
  misdated event) are excluded from the distribution; durations over
  2,000 days are kept in the distribution but separately flagged for
  manual review, since a ~5.5-year-plus gap is unusual enough to be
  worth a human look even if it's genuine.

## Versioning

`data/output/stats/headline_stats.json` carries `generated_at` (UTC)
and `code_commit` (the git commit the numbers were computed from) so a
consumer can tell which code version produced a given file.
