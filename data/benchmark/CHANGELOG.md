# Gold answer key changelog

## 2026-11-11 -- v12: added event_type "activist"

Added `"activist"` to `schemas.EventType` for activist-shareholder actions
(letters, director nominations, proxy contests, settlements, public
campaigns) aimed at the target, which had no distinct category before and
were scattered across `other`/`discussion`/`nda` depending on which specific
action they described.

Reclassified 9 events in `zendesk_gold.json` (JANA Partners' campaign against
Zendesk) from their prior event_type to `activist`:

| id | date | old event_type | summary |
|----|------|-----------------|---------|
| E02 | 2021-11-30 | other | Activist JANA Partners publicly opposes the Momentive deal |
| E05 | 2022-02-16 | other | JANA launches proxy contest (4 director nominees) and urges a sale |
| E07 | 2022-02-28 | other | JANA letter: board change or sale |
| E54 | 2022-06-07 | discussion | JANA refuses a limited NDA |
| E55 | 2022-06-08 | other | JANA announces intent to sue over the annual meeting |
| E65 | 2022-06-18 | nda | JANA signs limited-duration confidentiality agreement |
| E66 | 2022-06-19 | discussion | JANA supports engaging with the Consortium to improve price |
| E72 | 2022-06-21/2022-06-22 | discussion | JANA says it would not oppose a deal at $77.50 |
| E76 | 2022-06-23 | other | JANA agrees to withdraw nominations if a deal is announced |

Deliberately left unreclassified (they're the target board's own process
steps *about* the activist situation, not JANA's own action -- same
distinction the prompt already draws between "board_authorization" and the
conveyance it authorizes):

| id | date | event_type | summary |
|----|------|------------|---------|
| E18 | 2022-04-07 | discussion | Directors meet JANA; JANA wants board change or a sale |
| E60 | 2022-06-11 | board_authorization | Board authorizes settlement talks with JANA |
| E64 | 2022-06-15 | board_meeting | Board discusses expected Consortium proposal and JANA settlement |

`splunk_gold.json` has no activist-shareholder events; unchanged.
