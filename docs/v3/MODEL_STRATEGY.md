# S.A.G.A. v3 Model Strategy

Status: **DRAFT — BENCHMARK CANDIDATES, NOT ADOPTIONS**

The v3 architecture is model-independent. This document records the first challenger set and the intended role of each family.

## Adoption policy

A model is adopted only when it wins a S.A.G.A.-specific benchmark for its intended stage on quality, semantic safety, resource cost and license suitability.

External leaderboard rank alone is insufficient.

## 1. Semantic lexer

### GLiNER2 / GLiNER2.5-class models

Candidate role:

- schema-conditioned entity mentions;
- structured local extraction;
- local classifications;
- attributes/relations within bounded context;
- event-frame candidate harvesting.

Architectural status: **primary lexer challenger**.

Important limitation: this is a local semantic extraction layer, not a book-global identity/chronology engine. Chunk/window boundaries and relation co-occurrence constraints remain relevant.

License direction: Apache-2.0 implementation family; verify exact checkpoint/model-card license before pinning artifacts.

Benchmark against:

- existing BookNLP evidence;
- deterministic syntax/lexical baselines;
- pinned old GLiNER Small v2.1 result.

## 2. Global linker / cross-encoder family

### Ettin encoder/reranker family

Candidate roles:

- mention -> canonical candidate ranking;
- cluster-pair identity scoring;
- event-coreference pair scoring;
- temporal relation scoring;
- causal candidate scoring;
- scene-boundary classifier backbone;
- speaker classifier/joint scorer backbone.

Architectural status: **preferred first discriminative-model family to benchmark**.

The family spans small through larger encoders/rerankers, allowing S.A.G.A. to measure the smallest model that meets each task gate.

License direction: released Ettin rerankers are Apache-2.0; exact selected artifacts must be pinned and audited.

## 3. Structured extraction escalation

### NuExtract3

Candidate role:

- bounded difficult event-frame extraction;
- schema-conditioned proposition extraction;
- explicit attribute/relation normalization;
- fallback where the semantic lexer cannot produce a sufficiently complete structured frame.

Architectural status: **structured-generative challenger**, not a default whole-book pass.

License direction: current official NuMind model page reports Apache-2.0; exact revision must be pinned before use.

## 4. General semantic reasoning

### Qwen3.5 4B / 9B-class local models

Candidate role:

- final ambiguity adjudication;
- hard cross-sentence relation decisions;
- bounded state-delta reasoning;
- difficult causal/temporal adjudication;
- grounded higher-level summaries after compilation.

Architectural status: **final fallback, not primary extractor**.

Operational policy:

- structured/grammar-constrained output;
- non-thinking/direct mode for simple classification/adjudication where supported;
- thinking/reasoning only for hard residue;
- bounded evidence packets rather than repeated full-book prompts.

License direction: current Qwen3.5 model cards report Apache-2.0.

## 5. Existing BookNLP components

Candidate role: **v2 baseline and selective challenger**.

Retain only components that continue to win stage-specific benchmarks.

Current measured strengths include:

- event-trigger detection;
- useful speaker-attribution evidence.

Current measured weakness:

- primary character identity/canonicalization.

Package license: BookNLP repository/package is MIT. Model-weight/training-data suitability must still be recorded separately for production decisions.

## 6. Research-only long-context/coreference systems

### xCoRe

Role:

- architecture/reference point for cross-context identity resolution;
- benchmark/research ceiling where practical.

Do not adopt as production default under the current project policy because the released software/data are CC BY-NC-SA 4.0.

Use design ideas, not silent production dependency.

### Other research systems

Maverick/CorPipe/ModernBookNLP-style systems may be used as research ceilings if their exact code/model/data licenses permit local evaluation. They require an explicit entry in `MODEL_LICENSES.md` before any integration branch is merged.

## 7. S.A.G.A.-owned models

Long-term target:

- `SAGA-Lexer`
- `SAGA-Linker`
- `SAGA-Speaker`
- `SAGA-Scene`
- `SAGA-Event`
- `SAGA-Temporal`
- `SAGA-Causal`

External models initially serve as baselines, teachers and bootstrapping sources. Human-reviewed corrections should create training data so repetitive semantic decisions increasingly move to smaller task-specific models.

## 8. No-model tasks

The following should stay deterministic unless benchmark evidence proves otherwise:

- source fingerprinting;
- normalized offsets;
- source hierarchy;
- exact structural locators;
- current quote-boundary implementation while it remains the measured leader;
- narrative/source order;
- hard graph consistency checks;
- artifact fingerprints;
- run/provenance persistence.

## 9. Benchmark ordering

First-wave experiments:

1. GLiNER2-class lexer vs current BookNLP/old GLiNER evidence contracts.
2. Ettin-class identity linker vs current deterministic resolver + current provider evidence.
3. joint/specialist speaker challenger vs current combined v2 speaker pipeline.
4. scene-boundary encoder once gold scene annotations are ready.
5. NuExtract3 vs Qwen3.5 for difficult bounded event-frame extraction.
6. temporal and causal pair scorers only after event/event-coreference quality is stable.

## 10. Resource policy

For each task, prefer the smallest model that meets the semantic gate. A larger model is justified only by a measured improvement that matters at product level.

The target workstation class is a local consumer GPU with limited VRAM plus abundant system RAM; the architecture must not assume continuous residency of several large generative models.
