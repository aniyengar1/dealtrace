# Publication seed input correction

The existing seed generator always read the committed publication directory, even if a rehearsal/export had produced a different reviewed snapshot elsewhere. Using it in the scratch post-scoring flow would therefore regenerate the old pending copy rather than the isolated scored copy. The production default was internally consistent; the defect was the inability to select the intended alternate input explicitly.

The generator now accepts an explicit input directory and CLI `--input-dir`; non-default CLI input requires explicit `--output`. The default output remains byte-identical. Production generation rejects payloads marked synthetic. A library-only synthetic rehearsal mode emits conspicuous labels and an SQL guard requiring both the scratch database-name prefix and private temporary cluster data-directory prefix. It cannot silently apply a synthetic seed to the normal database.

Checks: five offline tests passed; one scratch DB integration test intentionally skipped before its separate execution. Tests were added under `earnings/tests/` to honor the owner's current earnings-only boundary. No production JSON/seed, website, guidance, live ledger, model code or source evidence was changed. No database connection or provider call was made by these unit tests.
