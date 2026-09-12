# Whole-Book Benchmark Protocol

Status: **ACTIVE PHASE-3 BENCHMARK FOUNDATION**

The whole-book benchmark exists to stop S.A.G.A. from selecting narrative-analysis providers from excerpts or academic corpora alone. It is deliberately provider-neutral and source-acquisition-neutral.

## Product qualification principle

S.A.G.A. is built for real modern novels and series. The primary acceptance corpus therefore uses the same contemporary/fantasy books that historically exposed the resolver's real failures:

- *Harry Potter and the Philosopher's Stone*;
- *The Cruel Prince*;
- *Caraval*;
- the ACOTAR series, with *A Court of Frost and Starlight* retained as the historical regression anchor.

LitBank remains useful as a reproducible public gold benchmark for metric decomposition and regression detection. It is **secondary evidence**. A candidate must not be promoted merely because it performs well on LitBank or another public-domain/classical corpus.

## Historical S.A.G.A. regression context

The previous full-book deterministic runs used:

- `max_chapters=999`;
- `max_windows=100000`;
- `paragraphs_per_window=3`;
- `overlap_paragraphs=1`.

They exposed product-relevant failures including:

- identity fragmentation: `Harry` / `Harry Potter`, `Dumbledore` / `Professor Dumbledore`, `Az` / `Azriel`, `Cardan` / `Prince Cardan`;
- real characters routed to supporting entities: `Hagrid`, `Snape`, `Neville`, `Cassian`, `Nesta`, `Rhys`, `Azriel`, `Tamlin`, `Julian`, `Taryn`, `Vivi`, `Valerian`, `Nicasia`;
- fantasy locations/groups/species promoted as characters: examples included `Illyrian Mountains`, `High Fae`, and `Castillo Maldito`;
- generic noun phrases flooding supporting entities.

Those classes of failure are first-class regression targets for the current v2 benchmark stack.

## What this runner proves

For each complete novel in a suite, the runner records:

- exact source byte count and SHA-256;
- provider/model/revision/license descriptor;
- exact provider command template fingerprint;
- wall-clock runtime;
- peak process-tree resident memory on supported Unix hosts;
- peak process-tree GPU memory when `nvidia-smi` is available;
- output file count/bytes;
- deterministic output-tree fingerprint excluding benchmark stdout/stderr logs;
- suite-level source and semantic-result fingerprints.

Runtime/resource measurements are kept separate from semantic fingerprints so a slower rerun can still prove identical source/provider output.

## Source boundary

The repository does **not** store the novels and the runner does **not** download them.

`services/analysis-worker/benchmarks/whole-book-primary-fiction-suite.v1.json` contains only the private suite metadata and expected filenames. The operator provisions lawful, user-owned source files outside the repository. At execution time the runner hashes the exact bytes actually used.

For copyrighted books:

- source text, extracted chapters, or reconstructive excerpts must never be committed;
- benchmark artifacts must contain only non-reconstructive metrics, fingerprints, counts, labels, failure categories, and bounded diagnostics;
- the benchmark harness must not automatically fetch commercial ebooks from the internet.

A benchmark artifact, not the repo manifest alone, is the authority for the exact source digest used in a run.

## Primary private fiction suite

The v1 primary suite contains:

1. *Harry Potter and the Philosopher's Stone* — honorifics, family surnames, organizations/locations, alias fragmentation;
2. *The Cruel Prince* — Fae personhood, titles, aliases, non-human characters, large cast;
3. *Caraval* — aliases, titles, identity reveal, location/name confusion;
4. *A Court of Thorns and Roses*;
5. *A Court of Mist and Fury*;
6. *A Court of Wings and Ruin*;
7. *A Court of Frost and Starlight* — historical S.A.G.A. regression anchor;
8. *A Court of Silver Flames*.

Additional contemporary books can be added later when they cover a genuinely new stressor. They should not displace these historical anchors without an explicit owner decision.

## Secondary public benchmark

LitBank remains valuable for:

- labelled mention/coreference metrics;
- deterministic regression tests;
- provider decomposition;
- repeatable public CI/manual experiments;
- comparing components under a shared gold standard.

But LitBank is not representative enough to act as the final promotion gate for S.A.G.A.'s modern fantasy/romantasy target workload. Its results must be reported as **secondary academic/regression evidence**, not as proof of production suitability.

## Invocation

The command after `--` is executed directly without a shell. It must contain both `{source}` and `{output}` placeholders; `{book_id}` is optional.

Example shape:

```bash
npm run benchmark:whole-book -- \
  --manifest benchmarks/whole-book-primary-fiction-suite.v1.json \
  --sources-root /benchmark/books \
  --output-root evaluation-artifacts/whole-books/provider-x \
  --report-out evaluation-artifacts/whole-books/provider-x.json \
  --provider-name provider-x \
  --provider-model model-y \
  --provider-revision exact-revision \
  --provider-license Apache-2.0 \
  -- python provider_runner.py --input {source} --output {output} --book-id {book_id}
```

The provider command owns task-specific output. The generic runner owns source/provenance/resource accounting.

## Promotion rule

A character/entity candidate may use LitBank to establish reproducible public metrics, but final adoption requires the private primary fiction suite. The acceptance decision must explicitly review modern-fantasy failure modes such as alias/title fragmentation, Fae/species/group confusion, person-vs-location typing, narrator/pronoun attachment, and real-character leakage into supporting/unresolved buckets.

One complete novel is enough to prove that the Phase-3 runtime can operate at book scale. It is **not** enough to prove product quality across S.A.G.A.'s target fiction.
