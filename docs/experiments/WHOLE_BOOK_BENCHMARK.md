# Whole-Book Benchmark Protocol

Status: **ACTIVE PHASE-3 BENCHMARK FOUNDATION**

The whole-book benchmark exists to stop S.A.G.A. from selecting narrative-analysis providers from excerpts alone. It is deliberately provider-neutral and source-acquisition-neutral.

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

`services/analysis-worker/benchmarks/whole-book-diversity-suite.v1.json` describes the intended complete-novel diversity set and expected filenames. The operator provisions lawful UTF-8 text files under a separate source directory. At execution time the runner hashes the exact bytes actually used.

This avoids:

- silently depending on a mutable download URL;
- committing public-domain or copyrighted book text merely for benchmarks;
- treating a Project Gutenberg identifier as proof that a work is public domain in every execution jurisdiction;
- contaminating private contemporary-book evaluation with repository artifacts.

A benchmark artifact, not the repo manifest alone, is the authority for the exact source digest used in a run.

## Public complete-novel diversity suite

The v1 suite covers twelve materially different works/forms:

- romance/social and honorific-heavy naming — *Pride and Prejudice*;
- gothic, epistolary and multiple narrators — *Dracula*;
- detective/mystery, aliases and first-person narration — *The Hound of the Baskervilles*;
- adventure, crews and nicknames — *Treasure Island*;
- science fiction and non-person entities — *The War of the Worlds*;
- children's fantasy and personified non-humans — *Alice's Adventures in Wonderland*;
- war, ranks and role nouns — *The Red Badge of Courage*;
- western/action-heavy naming — *Desert Gold*;
- modernist/experimental prose — *Ulysses*;
- non-human first-person protagonist — *Black Beauty*;
- large social ensemble — *Middlemarch*;
- multi-narrator identity-reveal mystery — *The Moonstone*.

This suite complements rather than replaces LitBank's gold-labelled 17-stratum evaluation. Whole books measure scale, resource behavior and qualitative failure modes; gold corpora remain necessary for precision/recall claims.

## Contemporary/private suite

No production character-analysis provider can be selected from public-domain classics alone. A later private suite must cover at least:

- contemporary fantasy / romantasy;
- contemporary romance;
- thriller / crime;
- modern science fiction;
- contemporary literary fiction;
- young adult;
- progression fantasy / LitRPG / web-serial style;
- fanfiction;
- English translated fiction;
- a very large ensemble or series installment.

Those source texts remain outside the repository. Only non-reconstructive benchmark metadata/results may be persisted.

## Invocation

The command after `--` is executed directly without a shell. It must contain both `{source}` and `{output}` placeholders; `{book_id}` is optional.

Example shape:

```bash
npm run benchmark:whole-book -- \
  --manifest benchmarks/whole-book-diversity-suite.v1.json \
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

A candidate that survives LitBank is not production-ready until it is run through the relevant complete-novel suite. Character/entity candidates must then also survive the private contemporary suite before adoption.

One complete novel is enough to prove the Phase-3 runtime can operate at book scale. It is **not** enough to prove cross-novel quality.
