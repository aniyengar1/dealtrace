# Owner budget update — $8 ceiling, inference paused

The owner lowered the total Crosscheck operational ceiling to **$8**, including every prior accounted amount and unresolved reservation. This does not authorize inference and is not a provider billing cap or a guarantee of shared Google Cloud trial credit. Owner-reported November project usage is approximately$279 of$300; remaining shared credit is uncertain and was not queried or inferred from a console banner.

Local verification:

|Item|USD|
|---|---:|
|Usage-based accounted amount, not Google invoice settlement|0.363525|
|Outstanding unresolved reservations|2.2373935|
|Original probe included in those reservations|1.12|
|Total occupied|2.6009185|
|New ceiling|8.00|
|Local ledger headroom|5.3990815|

Known subtotals remain informational, not extra charges added to held reservations. All11 attempt rows, their original amounts/statuses, and all prior events are preserved. One append-only budget-policy event records the update; nothing was reset, released or reclassified. Active calls0. No new provider requests, inference, CountTokens calls or retries occurred.

`earnings/hybrid/operational_policy.json` records the paused policy. Current code and config enforce the$8 ceiling atomically before reservation and explicitly block dispatch during owner review. Billing/payment, exhausted-credit, quota and conservative permission-error classifications stop dispatch without retry; they do not change billing, accounts or providers. Tests use fake errors only. The old quota-retry mock was changed to a generic503 legacy-transient fixture because quota retry is no longer allowed.

Completed v4 execution control files are preserved under `earnings/hybrid/archive/completed_v4/`. The active configuration version changed only for budget/pause/error controls; no prompt, schema, extractor rule or financial interpretation was tuned. Old request/response artifacts retain their actual v4 version and fingerprint. No inference has occurred under the new control version.

[Local verification](../validation/budget8_local_verification.json) records all amounts, untouched attempt rows and preserved prior events. The live-lock code, SQL guards, guidance and checkpoint tags are unchanged. Future calls need separate authorization and should target identified failure-resolution value, not repeat the completed ten releases because headroom remains.
