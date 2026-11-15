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

An anonymized placeholder ("Company A", "Party B", "Bidder 1" --
`src.entity_match.is_anonymized_placeholder`) is excluded from
candidacy entirely; it can never win by raw mention count even when
it's the most frequent name (parties often stay anonymous through
negotiation and get named only at signing -- see Global Blood
Therapeutics, where "Company A" outnumbered "Pfizer"). When frequency
finds no real candidate at all, the deal's latest signing event's
named party is used as a fallback (never as an override of an
already-good frequency answer -- doing that caused real regressions,
since a signing event's own language can be generic too, e.g. Lands'
End's signing event used "Purchaser" while an earlier proposal already
named "WHP Global"). A deal with no real name either way is set to
`acquirer='Unknown'`, an explicit unresolved marker.

**Known residual gap: stock-ticker-style self-references.** The
acronym check (`is_acronym_of`) catches initials-of-words tickers
("USS" for "UNITED STATES STEEL CORP") including ones that fold in a
legal-suffix letter ("MTI" for "Mechanical Technology Inc", "HCWC" for
"Healthy Choice Wellness Corp."). It cannot catch a ticker that isn't
derived from word-initials at all (a truncation like "MIRA" for "MIRA
Pharmaceuticals", or an arbitrary one like "FTAI" for "Fortress
Transportation & Infrastructure") -- there is no local, LLM-free way to
verify an arbitrary ticker against a company name without an external
ticker database. Three deals were left deliberately unresolved
(`acquirer='Unknown'`) rather than guessed, because the only candidate
name found looked ticker-like and self-referential but couldn't be
verified either way: Telomir Pharmaceuticals ("TELI"), Fortress
Transportation & Infrastructure Investors ("FTAI"), and Mobile
Infrastructure Trust ("MIC"). A handful of other ticker-like guesses
(KKR, OBDC, FSK, GBDC, PIF, GRI, GSP, HEL, LCIF, SKNY) were manually
verified against the deal's own proposals/signing-event context and
applied, since each clearly named a different real entity (often an
affiliated flagship fund absorbing a numbered-series sibling fund,
e.g. "FS KKR Capital Corp. II" being acquired by "FSK" = the original,
larger FS KKR Capital Corp).

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

## Postgres as the single source of truth (`src.deal_metrics`)

`deal_metrics` (one row per deal, canonical or not) and `headline_stats`
(one row per aggregate stat) hold the same numbers as
`headline_stats.json`, computed by the same per-deal functions in
`src.bulk_stats` so the two can never drift apart. `acquirer_display`
is a "best available" full name for the stored (often short-form)
acquirer: a small, deliberately curated lookup
(`deal_metrics.KNOWN_SHORT_NAME_EXPANSIONS`, e.g. "NSC" -> "Nippon
Steel Corporation") for the few cases verified with high confidence
where the full name never appears anywhere in the deal's own extracted
text; otherwise the longest locally-mentioned name that is a *literal,
safe* completion of the stored one (`deal_metrics._is_safe_fuller_name`)
-- guarded against several real false-positive patterns found while
building this: a reference to the acquirer ("SeaSpine" -> "SeaSpine
Board"), an anonymized-placeholder suffix ("Transocean" -> "Transocean
Party A"), two sponsors' names joined with "and", a bare ticker that
happens to start with this one's but names a different fund ("FSK" ->
"FSKR"), and a numbered sibling fund ("GBDC" -> "GBDC 3"). The curated
lookup is intentionally tiny -- a wrong guess there would be worse than
falling back to the short form -- so most short/ticker-form acquirers
with no fuller local mention are left as-is.

## Display names and price plausibility

`deal_metrics.target_display` and `.acquirer_display` are cleaned,
website-ready names: EDGAR legal suffixes ("Inc.", "Corp", "Holdings,
Inc.") and state-of-incorporation artifacts ("\DE\", "/DE/") stripped,
then title-cased (preserving a small curated list of known acronyms
like "PTC"/"ACV"/"BP" so they don't get lowercased into "Ptc"/"Acv"/
"Bp" -- see `src/display_name.py`). `acquirer_display` additionally
can never be a generic role placeholder ("Parent", "Buyer",
"Purchaser"), an anonymized placeholder ("Company A"), a board/
committee reference, a ticker/acronym that's actually the target
itself, or the target's own name under another form -- any of those
becomes `'Undisclosed'` instead. Across 1,125 deals (canonical and
non-canonical), **121 ended up `'Undisclosed'`** (mostly deals where
the underlying `deals.acquirer` was already "Parent"/"Unknown"/a
committee name, pre-existing from earlier acquirer-guess limitations,
not new failures from this display layer).

`deal_metrics.price_plausible` is `false` when the final price is
≤ $0.10/share or the final proposal is a quoted range rather than a
single settled price, `true` when neither applies, and `NULL` when
there's no final price at all to judge (393 of 1,125 deals).

## Versioning

`data/output/stats/headline_stats.json` carries `generated_at` (UTC)
and `code_commit` (the git commit the numbers were computed from) so a
consumer can tell which code version produced a given file; the same
two values are stored on every `headline_stats` row.
