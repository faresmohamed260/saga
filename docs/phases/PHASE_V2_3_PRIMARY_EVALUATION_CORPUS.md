# Phase 3 Amendment — Primary Evaluation Corpus

Status: **OWNER-DIRECTED ACTIVE AMENDMENT**

Date: 2026-09-12

This amendment supersedes the benchmark-corpus priority in section 9 of `PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md` wherever that section implies that LitBank or a public-domain/classical whole-book suite is sufficient for provider promotion.

## Owner direction

S.A.G.A. previously evaluated the deterministic identity resolver on modern fantasy/YA/romantasy books that better represent the intended product workload. Those materials, not LitBank, are the primary product qualification target.

The primary private suite is:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- the ACOTAR series, with *A Court of Frost and Starlight* retained as the historical regression anchor.

The repository stores only metadata and non-reconstructive diagnostics. Copyrighted source text remains private and outside Git.

## Recovered historical regression contract

The prior full-book runs used:

- `max_chapters=999`;
- `max_windows=100000`;
- `paragraphs_per_window=3`;
- `overlap_paragraphs=1`.

Important historical failures included:

- `Harry` vs `Harry Potter` and `Dumbledore` vs `Professor Dumbledore` fragmentation;
- `Az` vs `Azriel` fragmentation;
- `Cardan` vs `Prince Cardan` fragmentation;
- `Julian` incorrectly remaining supporting rather than canonical;
- real characters such as `Hagrid`, `Snape`, `Neville`, `Cassian`, `Nesta`, `Rhys`, `Tamlin`, `Taryn`, `Vivi`, `Valerian`, and `Nicasia` leaking into supporting entities;
- fantasy locations/groups/species such as `Illyrian Mountains`, `High Fae`, and `Castillo Maldito` being admitted too aggressively;
- supporting-entity pollution by ordinary noun phrases.

The historical Harry Potter chapter-one regression also checked that:

- `Mr. Dursley`, `Mrs. Dursley`, and `Mrs. Potter` canonicalize from story evidence;
- book-title/front-matter text cannot mint `Harry Potter`/`Harry` prematurely;
- `Grunnings` remains a group rather than a character;
- `Privet Drive` remains a location;
- standalone shared titles such as `Professor` do not become canonical characters.

These are product regressions and should be retained as explicit assertions or scored diagnostics where the current v2 architecture can express them.

## Role of LitBank

LitBank remains useful and should not be deleted. Its role is secondary:

- reproducible public gold metrics;
- component isolation;
- mention/coreference precision/recall decomposition;
- deterministic CI/manual regression;
- academic comparison across providers.

LitBank results do **not** by themselves authorize promotion of a character/entity provider into S.A.G.A.'s production path.

## Promotion rule

A candidate character/entity stack is eligible for adoption only after:

1. merge-gate synthetic/adversarial fixtures pass;
2. public/gold regression evidence such as LitBank is recorded where useful;
3. the candidate is run on the private primary fiction suite;
4. modern-fantasy failure modes are reviewed explicitly: alias/title fragmentation, Fae/species/group confusion, location/person confusion, narrator/pronoun attachment, character leakage into supporting/unresolved buckets, and series-scale identity stability;
5. source/model/config/resource fingerprints are preserved.

If public benchmark results and the private fiction suite disagree, the private fiction suite governs the product decision while the discrepancy is documented.
