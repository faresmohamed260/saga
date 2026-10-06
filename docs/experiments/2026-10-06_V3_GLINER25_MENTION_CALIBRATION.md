# 2026-10-06 — GLiNER2.5 Character-Mention Calibration

Status: **MEASURED — richer character-reference labels improve recall materially; GLiNER remains insufficient as the sole literary mention detector**

Capability under test: direct grounded character-mention extraction, isolated from identity clustering and merge policy.

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
- Transformers: `4.57.6`
- role: semantic-lexer challenger

The evaluator uses exact normalized-source spans. Duplicate predicted character spans are collapsed before scoring. Metrics are reported separately for proper names, nominals, and pronouns.

## Experiment 1 — single `person` label threshold sweep

Workflow run: `37469350815`

Artifact:

- ID: `11417145639`
- digest: `sha256:d573fecbf69feca23821e2b7f0e82be751f72ea9a8574788674b779eb913048f`
- qualification head: `5814f9f0126c47123974a9fd5ba8f5b41dbbc198`
- documents: `10`

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.4384 | 0.0911 | 0.1509 | 0.6761 | 0.0606 | 0.0021 |
| 0.50 | 0.4751 | 0.0868 | 0.1467 | 0.6761 | 0.0485 | 0.0007 |
| 0.65 | 0.5207 | 0.0820 | 0.1417 | 0.6640 | 0.0364 | 0.0007 |
| 0.75 | 0.5931 | 0.0746 | 0.1326 | 0.6275 | 0.0242 | 0.0007 |
| 0.85 | 0.6723 | 0.0694 | 0.1258 | 0.5992 | 0.0167 | 0.0007 |

The single generic label behaves primarily as a proper-name/entity seed detector. It does not establish that the model itself is incapable of reference mentions because GLiNER is label-conditioned.

## Experiment 2 — label-prompt comparison

Workflow run: `37472330494`

Artifact:

- ID: `11417900843`
- digest: `sha256:8da42e54b757802259d1cbe6dc00ee705d9bdffff5b36ce89428db24caaf278b`
- qualification head: `a39981a6c8216d7c47b37cd2affc2ad2ba6c2f24`
- documents: first `5` LitBank documents
- threshold: `0.5`

Three label configurations were evaluated independently on the same documents.

| Variant | GLiNER labels mapped to CHARACTER | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---|---|---:|---:|---:|---:|---:|---:|
| Generic | `person` | 0.7351 | 0.1052 | 0.1841 | 0.7883 | 0.0086 | 0.0000 |
| Person references | `person name`, `person description`, `person pronoun` | 0.7379 | 0.1735 | 0.2809 | 0.7883 | 0.0287 | 0.1140 |
| Character references | `character name`, `character description`, `character pronoun` | **0.7480** | **0.1801** | **0.2903** | 0.7883 | **0.0316** | **0.1246** |

### Interpretation

The richer label design changes the conclusion materially:

- pronoun recall is not intrinsically zero for this model; it rises from `0.0000` to `0.1246` with explicit character-reference labels;
- overall exact-span recall rises from `0.1052` to `0.1801`;
- precision also rises slightly from `0.7351` to `0.7480`, so the added reference labels did not create a simple precision-for-recall collapse on this sample;
- proper-name recall is unchanged at `0.7883`;
- nominal recall improves but remains very low (`0.0316`).

The leading measured prompt bundle is therefore:

`character name` + `character description` + `character pronoun`

This is a **challenger configuration**, not yet a production default. Five documents are too few for adoption and the nominal gap remains substantial.

## Current architectural consequence

The evidence supports a decomposed mention layer rather than one generic `person` query:

1. use explicit character/entity labels for strong canonical seeds;
2. use explicit reference-oriented labels when probing descriptions/pronouns;
3. benchmark nominal/reference coverage independently;
4. pass all grounded mentions into the separate high-recall identity candidate layer;
5. keep identity merge/abstain policy independent from lexer confidence.

A larger threshold calibration of the `character name, character description, character pronoun` bundle is the next justified GLiNER experiment. No production threshold is selected by this record.
