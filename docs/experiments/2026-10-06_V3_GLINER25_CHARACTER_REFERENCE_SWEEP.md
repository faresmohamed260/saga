# 2026-10-06 — GLiNER2.5 Character-Reference Threshold Sweep

Status: **MEASURED — richer labels remain the leading challenger; one shared threshold is not supported as the final policy**

This experiment follows the five-document label-prompt comparison and tests the leading label bundle on a larger 10-document LitBank sample.

## Fixed basis

LitBank:

- repository: `dbamman/litbank`
- commit: `3e50db0ffc033d7ccbb94f4d88f6b99210328ed8`
- annotation layer: `coref/tsv`
- documents: first `10`
- license: CC BY 4.0

Model:

- `fastino/gliner2.5-base-v1`
- revision: `ca906247640776a07753514055be9726f9080ead`
- labels mapped to `CHARACTER`:
  - `character name`
  - `character description`
  - `character pronoun`

The benchmark scores exact source spans and reports recall separately for LitBank proper names, nominals, and pronouns.

## Provenance

Workflow run: `37473999457`

Artifact:

- ID: `11418027932`
- digest: `sha256:9f39522df1c7ffc351a0bc9c3b8a4ffdce7067caee3bee3c86e211517fc54a32`
- qualification head: `51d661ecded0067f2c87b997d6004174f97a78ee`

## Results

| Threshold | Precision | Recall | F1 | Proper-name recall | Nominal recall | Pronoun recall |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.6272 | **0.1701** | **0.2676** | **0.8057** | **0.0530** | **0.1130** |
| 0.50 | 0.7306 | 0.1388 | 0.2333 | 0.7692 | 0.0348 | 0.0765 |
| 0.65 | 0.7934 | 0.1150 | 0.2008 | 0.7247 | 0.0242 | 0.0501 |
| 0.75 | 0.8156 | 0.0998 | 0.1778 | 0.6923 | 0.0227 | 0.0315 |
| 0.85 | **0.8421** | 0.0833 | 0.1516 | 0.6356 | 0.0121 | 0.0193 |

## Interpretation

The richer character-reference label bundle remains useful on the larger sample:

- proper-name recall remains strong across the sweep (`0.8057` at threshold `0.30`, `0.7692` at `0.50`);
- explicit character-pronoun prompting recovers a meaningful minority of pronouns (`0.1130` at threshold `0.30`), confirming the earlier near-zero generic-`person` result was partly a label-design artifact;
- nominal recall remains weak even at the most permissive measured threshold (`0.0530`);
- precision is highly tunable, rising from `0.6272` at `0.30` to `0.8421` at `0.85`;
- the best measured aggregate F1 is at `0.30`, but that threshold is not automatically the correct production choice because S.A.G.A. values canonical-seed precision differently from reference-mention coverage.

## Decision

A **single global confidence threshold across names, descriptions, and pronouns is not supported as the final design**.

The evidence points toward a typed confidence policy:

- character-name/canonical-seed evidence should favor substantially higher precision;
- character-pronoun/reference evidence can use a lower threshold because downstream candidate retrieval and mention-kind-aware ranking provide additional adjudication;
- nominal/description coverage remains insufficient and needs either better label design, a separate detector, or both.

The next justified GLiNER experiment is therefore a **multi-pass, label-specific threshold policy** rather than another global threshold sweep. A candidate design is:

1. run `character name` with a conservative threshold;
2. run `character pronoun` with a lower recall-oriented threshold;
3. benchmark `character description` / nominal-oriented labels independently;
4. union grounded spans with deterministic deduplication and retain label + confidence provenance;
5. send the resulting mentions to the separate V3 identity candidate/ranking layer.

No production threshold or merge policy is selected by this record.
