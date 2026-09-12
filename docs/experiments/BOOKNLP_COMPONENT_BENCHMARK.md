# BookNLP Public Speaker / Event Component Benchmark

Status: **BENCHMARK IMPLEMENTED — PUBLIC-GOLD RUN PENDING**

This experiment directly measures the BookNLP-small component roles that remained open after S.A.G.A. rejected it for primary character identity.

The benchmark is intentionally narrower than the identity benchmark. It asks two separate questions:

1. how well does BookNLP detect quotations and attribute speakers?
2. how well does BookNLP detect asserted literary event triggers?

Pinned LitBank is **secondary public/gold evidence**. These results can reject or narrow a candidate, identify useful component improvements and guide engineering work, but cannot by themselves promote a provider into production. The private modern-fiction suite remains the product gate.

## Fixed corpus

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- license: CC BY 4.0
- quote/speaker gold: `quotations/tsv`
- event-trigger gold: `events/tsv`
- identity mapping support: `coref/tsv`

The benchmark fails closed if the quotation source text differs from the coreference source text or if event TSV tokens drift from the source sentence/token structure.

## BookNLP candidate

The candidate provenance remains the same as the earlier measured identity experiment:

- official base commit: `3d900fc2224e55960c3363826ae28539b77b4204`
- compatibility commit: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- package metadata version: `1.0.7`
- model: `small`
- pipeline: `entity,quote,event,coref`
- code license: MIT
- model-weight license: **unverified**

The unverified weight license remains an adoption blocker regardless of quality.

## Speaker-isolation rule

BookNLP-small's primary identity/coreference quality is already known to be insufficient. Reusing BookNLP's predicted cluster ID as the speaker answer would therefore mix two errors together and make it impossible to tell whether speaker attribution itself is useful.

This benchmark instead takes BookNLP's attributed **speaker mention span** and maps that exact span to LitBank gold coreference. The resulting gold character ID becomes the predicted speaker key.

Therefore:

- a wrong attributed mention is a speaker-attribution error;
- a correct attributed mention receives the corresponding gold speaker identity;
- an attributed mention that cannot be uniquely mapped to gold remains unresolved;
- BookNLP's own cluster assignment does not receive credit or blame in this component score.

The benchmark records mention-to-gold mapping coverage explicitly so unresolved mapping cannot be hidden.

## Deterministic speaker comparison

S.A.G.A.'s existing deterministic dialogue/speaker floor is also scored against the same quotation gold.

To isolate the attribution heuristic rather than repeat identity errors, it receives a synthetic read-only identity layer generated from LitBank gold mentions and gold character IDs. This is labeled **oracle identity** throughout the report and must never be confused with production identity performance.

Metrics:

- exact quote precision / recall / F1;
- speaker accuracy on matched known-speaker quotes;
- resolved-speaker accuracy;
- unresolved rate;
- cross-character contamination;
- end-to-end speaker recall.

## Event comparison

LitBank event TSV labels are converted into exact source spans under the existing `saga-event-reference-v1` contract.

Both candidates are scored against exactly the same event-trigger gold:

- BookNLP-small event output;
- S.A.G.A.'s existing dependency-free lexical Tier-0 event floor.

Metrics:

- exact trigger precision / recall / F1;
- predicted/gold event counts;
- unsupported prediction count/rate;
- duplicate prediction count/rate.

LitBank's event layer does not supply S.A.G.A.-style actor/patient participant gold here, so participant grounding is explicitly **not scored**. A high trigger score must not be reported as participant-grounding success.

## Zero-gold documents

Some LitBank quotation files legitimately contain zero quote annotations. Those documents remain part of the benchmark.

- zero gold + zero predictions contributes no errors;
- zero gold + predictions contributes false positives.

This matters for precision and prevents benchmark inflation from dropping negative documents.

## Execution

Normal merge CI remains model-light and runs deterministic conversion/alignment/aggregation tests only.

The dedicated workflow `.github/workflows/v2-phase3-booknlp-components.yml` installs the previously measured pinned BookNLP compatibility environment, runs BookNLP-small over all pinned LitBank documents, then scores component output through S.A.G.A.'s provider-neutral evaluators.

The workflow publishes:

- component metrics in the GitHub Actions summary;
- BookNLP runtime, RAM and model-artifact measurements;
- a machine-readable component report with semantic fingerprint;
- per-document reports and failures.

## Interpretation policy

Public-gold results should be described as **component benchmark evidence**, not production qualification.

Progress means one of the following is demonstrated with numbers:

- higher quote/speaker quality than the deterministic floor;
- higher event-trigger quality than the lexical Tier-0 floor;
- useful precision/recall tradeoffs that justify a combined candidate;
- a clear failure mode that lets us reject or narrow BookNLP for that role.

No role is adopted until private modern-fiction qualification, repeatability, runtime/resource review, failure-mode review and production-compatible licensing are all satisfied.
