# BookNLP Public Speaker / Event Component Benchmark

Status: **PUBLIC-GOLD BENCHMARK COMPLETE AND REPEATABLE — NOT PRODUCTION QUALIFIED**

This experiment directly measures the BookNLP-small component roles that remained open after S.A.G.A. rejected it for primary character identity.

The benchmark intentionally asks separate questions:

1. how well does BookNLP detect quotation spans?
2. how well does BookNLP attribute speakers when its attributed mention span is mapped through trusted identity?
3. how well does BookNLP detect literary event triggers?

Pinned LitBank is **secondary public/gold evidence**. These results can reject or narrow a candidate, identify useful component improvements and guide engineering work, but cannot by themselves promote a provider into production. The private modern-fiction suite remains the product gate.

## Fixed corpus

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- license: CC BY 4.0
- documents attempted/completed/failed: `100 / 100 / 0`
- quote/speaker gold: `quotations/tsv`
- event-trigger gold: `events/tsv`
- identity mapping support: `coref/tsv`

The benchmark fails closed if the quotation source text differs from the coreference source text or if event TSV tokens drift from the source sentence/token structure.

## BookNLP candidate

The candidate provenance is unchanged from the earlier measured identity experiment:

- official base commit: `3d900fc2224e55960c3363826ae28539b77b4204`
- compatibility commit: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- package metadata version: `1.0.7`
- model: `small`
- pipeline: `entity,quote,event,coref`
- code license: MIT
- model-weight license: **unverified**

The unverified weight license remains an adoption blocker regardless of quality.

## Speaker-isolation rule

BookNLP-small's primary identity/coreference quality is already known to be insufficient. Reusing BookNLP's predicted cluster ID as the speaker answer would mix two error sources together.

This benchmark instead takes BookNLP's attributed **speaker mention span** and maps that exact span to LitBank gold coreference. The resulting gold character ID becomes the predicted speaker key.

Therefore:

- a wrong attributed mention is a speaker-attribution error;
- a correct attributed mention receives the corresponding gold speaker identity;
- an attributed mention that cannot be uniquely mapped to gold remains unresolved;
- BookNLP's own cluster assignment does not receive credit or blame in this component score.

The benchmark records mention-to-gold mapping coverage explicitly so unresolved mapping cannot be hidden.

## Deterministic speaker comparison

S.A.G.A.'s existing deterministic dialogue/speaker floor is scored against the same quotation gold.

To isolate attribution rather than repeat identity errors, it receives a synthetic read-only identity layer generated from LitBank gold mentions and character IDs. This is labeled **oracle identity** throughout the report and must never be confused with production identity performance.

## Measured results

Exact S.A.G.A. benchmark head:

`f013f23f11d2883e8ef1f2e70f9e181e8556df08`

### Quote detection

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | 0.7706 | 0.8640 | 0.8146 |
| S.A.G.A. deterministic quote floor | **0.8570** | 0.8555 | **0.8563** |

Interpretation: BookNLP gains about `+0.0085` absolute recall but loses about `-0.0864` absolute precision. The deterministic quote detector remains the stronger public-gold quote-boundary source.

### Speaker attribution

| Metric | BookNLP-small | Deterministic + oracle identity |
| --- | ---: | ---: |
| matched-known-speaker accuracy | **0.7830** | 0.3265 |
| resolved-speaker accuracy | **0.8057** | 0.5278 |
| end-to-end speaker recall | **0.6765** | 0.2793 |
| unresolved rate on matched known-speaker quotes | **0.0282** | 0.3815 |
| cross-character contamination | **0.1889** | 0.2921 |

BookNLP attributed `1,978` speaker mentions; `1,863` mapped uniquely to LitBank gold identity, for mapping coverage `0.9419`.

Interpretation: BookNLP is a strong speaker-attribution challenger and substantially improves recall and accuracy over the current deterministic attribution heuristic, but `18.89%` cross-character contamination is still too high for direct canonical adoption.

### Event-trigger detection

| Candidate | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| BookNLP-small | **0.8003** | **0.7591** | **0.7791** |
| S.A.G.A. lexical Tier-0 | 0.4914 | 0.0585 | 0.1045 |

BookNLP improves trigger F1 by about `+0.6746` absolute over the lexical Tier-0 floor.

Participant grounding is **not scored** by this LitBank layer. A strong trigger result must not be reported as solved event extraction.

## Repeatability

Two independent GitHub-hosted CPU runs on the exact same S.A.G.A. SHA, pinned LitBank commit and pinned BookNLP environment produced the exact same semantic report fingerprint:

`e0ec94d8d1f678f98057a29117d365926a3253a4a6d5e6e0f7c96e36cab3bef9`

Run 1:

- wall clock: `452.68 s`
- peak RSS: `1123.8 MiB`
- model artifacts: `160,398,571 bytes` (~153 MiB)
- documents: `100 / 100 / 0 failed`

Run 2:

- wall clock: `293.66 s`
- peak RSS: `1157.2 MiB`
- model artifacts: `160,398,571 bytes`
- documents: `100 / 100 / 0 failed`

Runtime variation is expected across hosted runners; identical semantic fingerprints establish deterministic scored output for these two runs.

## Test qualification

The benchmark head passed all repository qualification gates:

- Required Check Compatibility;
- S.A.G.A. v2 Analysis Worker CI;
- S.A.G.A. v2 LitBank Oracle Baseline;
- Backend Architecture CI.

The heavyweight workflow also passed analysis-worker typecheck and `111 / 111` tests on both measured attempts.

## Important generalization caveat

BookNLP's speaker/event components are trained on LitBank-derived literary annotations. This benchmark is therefore strong public regression/component evidence but is not an independent modern-fiction generalization test.

That is another reason the owner-controlled modern-fiction suite remains the production promotion gate.

## Architecture decision from this experiment

The evidence supports a split challenger rather than replacing S.A.G.A.'s deterministic stack wholesale:

- **quote spans:** keep S.A.G.A.'s deterministic quote detector as the stronger public-gold boundary source;
- **speaker attribution:** continue BookNLP as a restricted evidence challenger, mapped through S.A.G.A.-resolved identity and confidence-gated because contamination remains material;
- **event triggers:** continue BookNLP as the leading trigger challenger;
- **event participants:** build and measure dependency-aware deterministic grounding separately;
- **primary identity:** BookNLP remains rejected.

Follow-up work is tracked in issues `#213` and `#214`.

## Zero-gold documents

Some LitBank quotation files legitimately contain zero quote annotations. Those documents remain part of the benchmark.

- zero gold + zero predictions contributes no errors;
- zero gold + predictions contributes false positives.

This prevents benchmark inflation from dropping negative documents.

## Interpretation policy

No role is production-adopted until private modern-fiction qualification, repeatability, runtime/resource review, failure-mode review and production-compatible licensing are all satisfied.
