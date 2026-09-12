# 2026-09-12 — Character Identity Candidate: BookNLP Small

Status: **CANDIDATE — no production adoption decision**

Capability under test: character/entity evidence, coreference attachment, quote-speaker evidence, literary event triggers.

The purpose of this record is to preserve both successful and failed BookNLP experiments. BookNLP is not a production dependency merely because it is being benchmarked.

## Fixed comparison basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer used for identity scoring: `coref/tsv`
- license: CC BY 4.0

S.A.G.A. oracle-evidence policy baseline over all 100 LitBank documents:

- canonical precision: `0.9516`
- canonical recall: `0.9970`
- incorrect-merge rate: `0.0000`
- fragmentation rate: `0.1422`
- linked-mention precision: `0.9942`
- non-person quarantine rate: `1.0000`

The oracle baseline is an upper-bound/policy diagnostic: it feeds LitBank gold entity/coreference evidence into S.A.G.A. It does **not** measure a real provider's mention/coreference recall.

## Candidate source

Official BookNLP base:

- repository: `booknlp/booknlp`
- base commit: `3d900fc2224e55960c3363826ae28539b77b4204`
- package metadata version: `1.0.7`
- repository code license: MIT

Model-weight license: **unverified**. The official code repository downloads the model files from Berkeley but does not provide a separate model-weight license declaration that S.A.G.A. has verified. A third-party mirror labeling the weights MIT is not sufficient provenance for production adoption.

## Experiment 1 — official base with unconstrained 2026 dependencies

GitHub Actions run: `34699510439`

S.A.G.A. commit:

- `30feff55b8da5c44b4f14aab7c4fc9a6717601a4`

Requested workload:

- BookNLP `small`
- pipeline `entity,quote,event,coref`
- first 5 sorted LitBank `coref/tsv` documents
- CPU GitHub-hosted Ubuntu runner

Resolved environment from the run:

- Python `3.10.21`
- BookNLP `1.0.7`
- spaCy `3.8.16`
- PyTorch `2.14.0`
- TensorFlow `2.21.0`
- Transformers `5.17.0`

### Result

**FAILED during BookNLP initialization before any document was processed.**

Failure:

```text
RuntimeError: Error(s) in loading state_dict for Tagger:
Unexpected key(s) in state_dict: "bert.embeddings.position_ids".
```

This is a known upstream compatibility problem. Upstream PR `booknlp/booknlp#25` contains an unmerged narrow fix that removes the obsolete `bert.embeddings.position_ids` key from the three BookNLP state dictionaries before loading them.

### Operational observation

The unconstrained install is not a credible production environment:

- it pulled modern GPU-enabled PyTorch/CUDA packages on a CPU runner;
- it installed TensorFlow even though no TensorFlow import was found in the current BookNLP source outside dependency declaration;
- individual downloads included hundreds-of-megabytes artifacts for TensorFlow, PyTorch, cuDNN, cuBLAS, Triton and other CUDA libraries;
- the dependency installation therefore consumed several gigabytes before model initialization failed.

This is retained as a negative result. It shows that `pip install BookNLP` with unconstrained 2026 dependencies is not suitable as S.A.G.A.'s production installation strategy even if later quality metrics prove competitive.

## Experiment 2 — compatibility-patched, CPU-bounded environment

GitHub Actions run: `34699861942`

S.A.G.A. commit:

- `068734bbe05511ee6146bd0c5c3cf12cced53c80`

Code:

- official upstream base: `3d900fc2224e55960c3363826ae28539b77b4204`
- exact open PR-25 compatibility head: `8875a1b616d764b7d13d1e30e9949cc21ca303c1`

Pinned environment attempted:

- Python `3.10.21`
- PyTorch `2.3.1+cpu`
- spaCy `3.7.5`
- Transformers `4.43.4`
- BookNLP fork commit installed with `--no-deps`
- TensorFlow deliberately omitted because it is not imported by the active BookNLP runtime source

### Result

**FAILED during environment setup before BookNLP inference.**

The bounded dependency strategy itself worked: CPU-only PyTorch resolved to a `190.4 MB` wheel and avoided the prior CUDA/TensorFlow dependency explosion. The run then failed when invoking the spaCy CLI because `click` was not present in the resolved environment:

```text
ModuleNotFoundError: No module named 'click'
```

Classification: **benchmark-environment configuration failure**, not provider-quality evidence. No document was processed and no S.A.G.A. quality metric was produced.

## Experiment 3 — bounded compatibility environment, 5-document smoke

GitHub Actions run: `34699944924`

S.A.G.A. experiment head:

- `b961a06f65c61a43828971b8d642f8ec51514124`

Artifact:

- name: `saga-phase3-booknlp-small-smoke`
- artifact ID: `10299318866`
- digest: `sha256:1dd92ea2d03f2abc8ed1dd2ad054e715f2bbaf37309e033c125d0b26ddc22e69`

Pinned environment:

- Python `3.10.21`
- PyTorch `2.3.1+cpu`
- Click `8.1.7`
- spaCy `3.7.5`
- Transformers `4.43.4`
- BookNLP compatibility commit `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- TensorFlow not installed

### Result

**SUCCESSFUL end-to-end provider run and S.A.G.A. evaluation.**

All 5 attempted LitBank documents completed with no provider/evaluator failure.

Quality after BookNLP evidence was normalized and passed through the existing deterministic S.A.G.A. identity resolver:

- gold seed-eligible characters: `36`
- predicted canonicals: `61`
- pure canonicals: `19`
- false canonicals: `22`
- incorrect merges: `10`
- contaminated canonicals: `38`
- represented gold characters: `17`
- fragmentation excess: `15`
- relevant gold mentions: `552`
- correct linked mentions: `75`
- linked mentions: `299`
- canonical precision: `0.3115`
- canonical recall: `0.4722`
- false-canonical rate: `0.3607`
- incorrect-merge rate: `0.1639`
- contaminated-canonical rate: `0.6230`
- fragmentation rate: `0.4167`
- linked-mention precision: `0.2508`
- linked-mention recall: `0.1359`
- unresolved relevant mention rate: `0.4964`
- non-person quarantine rate: `0.9583`
- cluster purity: `0.8510`

Aggregate semantic output fingerprint:

- `fa96751cbdb4d45e99e758187c83bdccd57eaee37fdae8ca1ec9fc796b188a5a`

### Operational result

- initialization: `15.57 s`
- total wall clock for 5 documents: `32.78 s`
- peak resident memory: `883.6 MiB`
- GPU: none
- peak VRAM: none
- BookNLP model artifacts: `160,398,571 bytes` (`~153 MiB`)

Exact downloaded model artifacts:

- coreference: `40,831,851 bytes`, SHA-256 `eadd62a0b5d6f1d8908ee31c9949f863b731046e0e64df8c0c46bedf07a56116`
- entities: `61,979,735 bytes`, SHA-256 `0620eed33c32c9b15dcbf3303bb3809b4f7ea29eef5311ba55db361a848cda5a`
- speaker: `57,586,985 bytes`, SHA-256 `1f530622219b8d6d90881f0d2eaeeec08ff6b73287d9eac66a1505ee0e6887e5`

### Interpretation

The operational footprint is attractive once the environment is pinned correctly, but the **identity quality is not close to production-grade in this smoke set**. In particular, false canonicals, cross-character merges, contaminated canonicals, and linked-mention precision are far worse than the oracle-policy baseline.

This is evidence against using BookNLP-small coreference/identity output as S.A.G.A.'s primary canonical identity provider in its current form. It is **not yet a final rejection**, because five documents are insufficient for a durable full-corpus conclusion and BookNLP may still be useful for narrower roles such as quote/speaker evidence, event triggers, syntax, or auxiliary mention evidence.

## Experiment 4 — same pinned candidate, full 100-document LitBank run

Status: **IN PROGRESS**

No provider/model/runtime change is allowed from Experiment 3. The same exact environment and compatibility commit are expanded from 5 to all 100 pinned LitBank documents so the identity conclusion is based on the full literary benchmark rather than the smoke subset.

The full run is intended to answer:

1. whether the poor smoke identity precision/merge behavior persists over all 100 documents;
2. whether provider failures appear at larger corpus scale;
3. whole-corpus runtime and memory behavior;
4. whether any BookNLP sub-capability remains promising enough to benchmark separately rather than discarding the package wholesale.

## Decision rule

No decision is made from published BookNLP benchmark numbers or from a successful smoke run.

Before adoption, S.A.G.A. requires at minimum:

1. real provider quality results on the pinned literary evaluation set;
2. whole-book runtime/RAM/VRAM/model-size evidence;
3. at least two completed repeatability runs for the candidate configuration;
4. failure-mode documentation;
5. direct comparison with other viable candidates such as GLiNER/F-Coref combinations;
6. acceptable operational maintainability;
7. verified licensing for both code and required model artifacts.

A candidate that is slower or larger may still win if it is materially more reliable. A candidate that is lightweight may still be rejected if its identity contamination, merge behavior, speaker attribution, event evidence, maintenance burden, or licensing is not production-grade.
