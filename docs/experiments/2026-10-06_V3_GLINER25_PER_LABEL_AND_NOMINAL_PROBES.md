# 2026-10-06 — GLiNER2.5 Per-Label and Nominal-Reference Probes

Status: **MEASURED — mixed character-reference prompting retained as the leading GLiNER challenger; standalone label passes and nominal-oriented labels rejected as sufficient mention detectors**

These experiments follow the direct GLiNER2.5 mention-calibration work and test two hypotheses:

1. whether the leading mixed `character name + character description + character pronoun` bundle can be decomposed into cleaner label-specific passes; and
2. whether alternative nominal/reference labels can recover literary nominals such as `the doctor`, `her brother`, or `the old man` well enough to avoid a separate mention detector.

Neither hypothesis is supported by the measured results.

## Fixed basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- license: CC BY 4.0

Model:

- `fastino/gliner2.5-base-v1`
- revision: `ca906247640776a07753514055be9726f9080ead`
- GLiNER2 package: `2.0.0`
- CPU inference

The evaluator scores exact character-mention spans and reports recall separately for proper names, nominals, and pronouns.

## Experiment 1 — standalone label threshold sweeps

Workflow run: `37475097824`

Artifact:

- ID: `11418749413`
- digest: `sha256:5aee9cd273c2821fd5e1e96bd0ab517c432b9bbed67c9db2717d1dca83221533`
- qualification head: `566298e9656edee1ac6de1b2e2279e63e5b4f5ac`
- documents: first `10` LitBank documents

### `character name`

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.7244 | 0.0889 | 0.1584 | **0.7895** | 0.0152 | 0.0000 |
| 0.50 | 0.7625 | 0.0863 | 0.1551 | 0.7733 | 0.0121 | 0.0000 |
| 0.65 | 0.7833 | 0.0816 | 0.1477 | 0.7287 | 0.0121 | 0.0000 |
| 0.75 | 0.7945 | 0.0755 | 0.1379 | 0.6761 | 0.0106 | 0.0000 |
| 0.85 | **0.8298** | 0.0677 | 0.1252 | 0.6113 | 0.0076 | 0.0000 |

Result: useful explicit-name seed behavior, but not a reference detector.

### `character description`

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.6211 | 0.0434 | 0.0811 | 0.3927 | 0.0045 | 0.0000 |
| 0.50 | 0.7244 | 0.0399 | 0.0757 | 0.3603 | 0.0045 | 0.0000 |
| 0.65 | 0.7778 | 0.0364 | 0.0696 | 0.3279 | 0.0045 | 0.0000 |
| 0.75 | 0.8022 | 0.0317 | 0.0609 | 0.2834 | 0.0045 | 0.0000 |
| 0.85 | **0.8312** | 0.0278 | 0.0537 | 0.2470 | 0.0045 | 0.0000 |

Result: the label mostly fires on names and contributes essentially no nominal coverage.

### `character pronoun`

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.7194 | **0.1046** | **0.1826** | 0.6680 | 0.0288 | **0.0408** |
| 0.50 | 0.7615 | 0.0720 | 0.1316 | 0.5587 | 0.0152 | 0.0129 |
| 0.65 | 0.7904 | 0.0573 | 0.1068 | 0.4939 | 0.0091 | 0.0029 |
| 0.75 | 0.8521 | 0.0525 | 0.0989 | 0.4656 | 0.0091 | 0.0000 |
| 0.85 | **0.8870** | 0.0443 | 0.0843 | 0.3927 | 0.0076 | 0.0000 |

Result: even a `character pronoun` query is dominated by proper-name predictions. At threshold `0.30`, pronoun recall is only `0.0408`.

### Comparison to the mixed bundle

On the same 10-document basis, the mixed labels `character name + character description + character pronoun` at threshold `0.30` previously measured:

- precision: `0.6272`
- overall recall: `0.1701`
- proper-name recall: `0.8057`
- nominal recall: `0.0530`
- pronoun recall: **`0.1130`**

The mixed bundle therefore recovers almost three times as many pronouns as the standalone `character pronoun` pass (`0.1130` versus `0.0408`) while also improving proper-name and nominal recall.

**Interpretation:** the useful reference behavior is partly a multi-label conditioning interaction. A design that assumes independent label-specific passes can be calibrated in isolation is not supported by this model's measured behavior.

## Experiment 2 — nominal/reference label probe

Workflow run: `37475208648`

Artifact:

- ID: `11419341524`
- digest: `sha256:aaac0cd441d7a926921cdc896d4279f37c1393b68535fad832c09e712099b7c8`
- qualification head: `e5bd7f1b208a0ccca2ce91de2ce135f5bd2f5580`
- documents: first `5` LitBank documents
- thresholds: `0.30`, `0.50`

Best nominal recall measured for each tested label:

| Label | Threshold | Precision | Nominal recall | Proper-name recall | Pronoun recall |
|---|---:|---:|---:|---:|---:|
| `character description` | 0.30 | 0.6324 | 0.0000 | 0.3139 | 0.0000 |
| `character role` | 0.30 | 0.6696 | 0.0057 | 0.5328 | 0.0000 |
| `character title` | 0.30 | 0.7338 | 0.0086 | 0.7226 | 0.0000 |
| `character reference` | 0.30 | 0.7391 | 0.0029 | 0.6131 | 0.0000 |
| `person description` | 0.30 | 0.6890 | 0.0115 | 0.7883 | 0.0018 |
| `person role` | 0.30 | 0.6111 | **0.0287** | 0.7299 | 0.0000 |
| `person reference` | 0.30 | 0.7124 | 0.0115 | 0.7664 | 0.0000 |

The best tested nominal recall is only `0.0287`. Most predictions still behave like explicit person/name detection despite nominal-oriented label wording.

## Decision

The evidence now supports a narrower role for GLiNER2.5 in S.A.G.A. V3:

- **retain GLiNER as a strong explicit-character/name seeding provider;**
- retain the mixed `character name + character description + character pronoun` bundle as a **supplemental reference-mention challenger**, because it outperforms the isolated labels;
- **do not treat GLiNER confidence as a clean mention-kind-specific probability**;
- **do not implement separate production thresholds per standalone GLiNER label based on these experiments**;
- **do not rely on GLiNER for nominal coverage**; a separate nominal/reference detector is required;
- preserve label/confidence/provider provenance when multiple mention providers are combined;
- keep identity candidate retrieval, ranking, and merge/abstain policy separate from mention detection.

The next justified architecture is therefore a composite mention layer:

`high-precision explicit-name provider` + `supplemental GLiNER mixed-reference provider` + `separate nominal/pronoun/reference detector(s)` → deterministic grounded-span union/deduplication → V3 hybrid identity retrieval → mention-kind-aware ranking → conservative merge/abstain policy.

No production merge threshold or canonical-link decision is selected by these experiments.
