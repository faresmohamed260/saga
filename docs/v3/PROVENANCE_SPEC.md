# S.A.G.A. v3 Provenance and Artifact Specification

Status: **DRAFT v0 — CORE INVARIANT**

Every semantic result must be explainable as a deterministic chain from source bytes, stage configuration and model/runtime artifacts.

## 1. Provenance questions every accepted fact must answer

- Which source document produced this?
- Which exact source span(s) support it?
- Which stage proposed it?
- Which model/rule/provider produced the proposal?
- Which exact model/config version was used?
- Which resolver/solver/policy accepted it?
- Which earlier artifacts did it depend on?
- Was it human-reviewed?
- Has it been superseded or contradicted?

## 2. Artifact identity

Every stage output has a content-addressed fingerprint derived from:

```text
stage_name
stage_version
ordered input artifact fingerprints
producer name/version
model artifact fingerprint if applicable
configuration fingerprint
normalization/ontology/IR versions relevant to interpretation
```

Recommended serialization:

1. canonical JSON with stable key ordering;
2. UTF-8;
3. SHA-256.

## 3. Source fingerprint

The source identity begins with immutable uploaded bytes and a separate normalized-source fingerprint.

Do not use filenames as identity.

Store:

- raw object hash/fingerprint;
- normalization version;
- normalized text hash;
- structural compiler version.

## 4. Model artifact fingerprint

For local model inference, record where practical:

- repository/model ID;
- exact revision/commit;
- selected files;
- quantization variant;
- artifact SHA-256 or model-manifest fingerprint;
- tokenizer revision;
- runtime/library version.

A label such as `Qwen3.5-9B-Q4` is insufficient provenance.

## 5. Configuration fingerprint

Stage configuration includes every semantic threshold or option capable of changing output, including:

- schemas/labels;
- confidence thresholds;
- chunk/window size;
- overlap;
- candidate top-k;
- merge thresholds;
- solver policy;
- prompt/template revision;
- grammar/JSON schema revision;
- random seed where relevant.

## 6. Evidence references

Semantic records reference canonical `SourceSpan` IDs. Raw copied excerpts are optional display caches and are not evidence identity.

Offsets must be validated against the normalized source fingerprint before commit.

## 7. Decision trail

For merge/link/canonicalization decisions record:

- candidates considered;
- candidate scores;
- selected decision;
- hard constraints that fired;
- rejection reasons;
- escalation reason if a stronger model was invoked.

The minimum trail should support post-hoc debugging without rerunning every model.

## 8. Human review provenance

Human corrections record:

- reviewer identity;
- original model/policy prediction;
- correction;
- review timestamp;
- annotation/task version.

Human review does not erase the original prediction.

## 9. Cache semantics

A stage cache entry is reusable only when its complete artifact fingerprint matches.

Never reuse based only on:

- filename;
- book ID;
- model display name;
- stage name.

## 10. Supersession

When a newer run produces a different accepted interpretation:

- old evidence remains stored;
- old accepted facts become superseded where appropriate;
- links to the superseding fact/run are recorded;
- historical product outputs remain reproducible by run/version.

## 11. Derived materializations

Neo4j projections, vector indexes, summaries, profiles and image prompts record the canonical IR/run fingerprint from which they were built.

They may be deleted/rebuilt without data loss.

## 12. Reproducibility level

Each stage declares one of:

- `deterministic`: identical canonical input/config -> identical output expected;
- `seeded`: deterministic under pinned runtime/seed within defined tolerance;
- `stochastic`: semantic equivalence expected, byte equality not guaranteed.

Benchmarks should prefer deterministic/seeded modes where model capability permits.
