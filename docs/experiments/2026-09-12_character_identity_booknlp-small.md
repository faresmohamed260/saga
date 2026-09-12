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

This is a distinct candidate configuration rather than rewriting Experiment 1.

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

The next attempt keeps the same candidate code/model configuration and adds an explicit `click==8.1.7` pin. This is the only material environment correction.

## Experiment 3 — bounded compatibility environment with explicit CLI dependency

Status: **IN PROGRESS**

S.A.G.A. commit beginning the attempt:

- `b961a06f65c61a43828971b8d642f8ec51514124`

Pinned environment:

- Python `3.10`
- PyTorch `2.3.1` CPU wheel
- Click `8.1.7`
- spaCy `3.7.5`
- Transformers `4.43.4`
- BookNLP compatibility commit `8875a1b616d764b7d13d1e30e9949cc21ca303c1`
- no TensorFlow installation

Initial workload remains the same five pinned LitBank documents. Only after this smoke run succeeds will the same fixed configuration be expanded to all 100 documents.

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
