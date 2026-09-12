# Primary Fiction Regression Recovery — 2026-09-12

Status: **ACTIVE PHASE-3 PRODUCT REGRESSION RECORD**

## Why this record exists

The Phase-3 benchmark reset initially over-weighted LitBank/public literary corpora. The owner corrected that direction: S.A.G.A.'s primary qualification material is the modern fantasy/YA/romantasy suite historically used during development.

This record captures the non-reconstructive regression facts recovered from the May 2026 experiments so future work does not need to reconstruct them from chat history or private local paths.

No copyrighted source text is stored here.

## Historical execution shape

Recovered full-book resolver runs used:

- `max_chapters=999`
- `max_windows=100000`
- `paragraphs_per_window=3`
- `overlap_paragraphs=1`

Historical bounded smoke tests used:

- ACOFAS: first chapter, first 4 windows, 3 paragraphs/window, overlap 1
- Harry Potter opening regression: first chapter, first 6 windows, 3 paragraphs/window, overlap 1

## Recovered real-book failures

### Harry Potter and the Philosopher's Stone

- `Harry` and `Harry Potter` fragmented into separate canonicals.
- `Dumbledore` and `Professor Dumbledore` fragmented into separate canonicals.
- `Hagrid`, `Snape`, and `Neville` appeared in the old supporting layer despite being real characters.
- historical full-book counts: `canonical=189`, `temporary=166`, `quarantine=293`, `supporting=5283`.

Opening-chapter assertions from the historical regression test:

- `Mr. Dursley` canonicalizes;
- `Mrs. Dursley` canonicalizes;
- `Mrs. Potter` canonicalizes from in-story evidence;
- title/front-matter `Harry Potter` and `Harry` do not mint canonicals prematurely;
- `Grunnings` is not a character;
- `Privet Drive` is not a character;
- standalone shared title `Professor` is not a canonical character;
- front-matter fragments do not mint canonicals.

### A Court of Frost and Starlight

- `Azriel` and `Az` fragmented.
- `Cassian`, `Nesta`, `Rhys`, `Azriel`, and `Tamlin` appeared in the old supporting layer.
- false canonical admissions included `Illyrian Mountains`, `High Fae`, and `Not Cassian`.
- historical full-book counts: `canonical=46`, `temporary=33`, `quarantine=112`, `supporting=5303`.

Historical opening smoke:

- `Feyre` canonicalizes;
- `High Lady` does not stand alone as a canonical character;
- `Night Court` is not a character.

### Caraval

- `Scarlett`, `Tella`, `Dante`, and `Legend` were surfaced strongly.
- `Julian` remained supporting rather than canonical — a major miss.
- `Castillo Maldito` was admitted as a character incorrectly.
- `Caraval Master Legend` was flagged as title/name confusion; the current regression manifest intentionally does **not** encode a hard merge relation until a fresh run establishes the intended relation unambiguously.
- historical full-book counts: `canonical=55`, `temporary=54`, `quarantine=174`, `supporting=5877`.

### The Cruel Prince

- `Cardan` and `Prince Cardan` fragmented.
- `Taryn`, `Vivi`, `Valerian`, and `Nicasia` appeared in the old supporting layer.
- historical full-book counts: `canonical=60`, `temporary=218`, `quarantine=153`, `supporting=7321`.

The large temporary count was a clear sign of hesitation/noise, but the current v2 result model does not yet expose an equivalent `temporary` bucket. The historical number is preserved as evidence rather than invented into a new hard threshold.

## Regression implementation

Machine-readable expectations live at:

- `services/analysis-worker/benchmarks/primary-fiction-regression-expectations.v1.json`

Evaluator:

- `services/analysis-worker/src/evaluation/primary-fiction-regression.ts`

CLI:

- `npm run benchmark:primary-fiction-regression -- --expectations <manifest> --case <case-id> --result <identity-result.json> [--out <report.json>]`

The evaluator distinguishes:

- required canonical surfaces;
- alias/title surface groups that must resolve to one canonical character;
- surfaces forbidden from becoming canonical identities;
- surfaces forbidden from being linked to any character.

Opening-chapter cases and full-book cases are separate. This prevents historically valid assertions such as “Harry must not canonicalize from title/front matter yet” from being incorrectly applied to a complete-book result.

## Product decision rule

LitBank remains useful for reproducible public metrics and component isolation. It is not the product acceptance target.

A provider stack cannot be adopted for character identity until it is tested against these private real-book regressions and the broader primary fiction suite. If a public benchmark looks strong but these regressions fail, the provider is not production-ready for S.A.G.A.
