# S.A.G.A. Documentation Index

This file is the navigation layer for S.A.G.A. documentation. It intentionally **does not duplicate volatile current branch, PR, commit, or workflow state**.

For the current high-level project handoff and phase status, read [`../PROJECT.md`](../PROJECT.md). Git history is authoritative for exact merge state.

## Read first

For substantial current work, use this order:

1. [`../AGENTS.md`](../AGENTS.md) — repository/AI development instructions.
2. [`../PROJECT.md`](../PROJECT.md) — current project handoff and phase status.
3. [`DECISIONS.md`](DECISIONS.md) — durable architecture/product decisions.
4. The active phase contract referenced by `PROJECT.md`.
5. Any active owner-directed phase amendment.
6. The relevant current `v2/` architecture/runtime contract.
7. The relevant `validation/` scorecard or qualification record.
8. Detailed evidence under `experiments/` when a decision depends on measurements.

## Documentation ownership

Use one source for each kind of truth:

| Source | Owns |
| --- | --- |
| `../README.md` | Public project overview, product positioning, quick start, stable architecture summary |
| `../PROJECT.md` | Current high-level phase/capability handoff |
| `DECISIONS.md` | Durable adopted decisions and constraints |
| `phases/` | Phase contracts, scope, exit criteria, amendments |
| `v2/` | Current v2 architecture and runtime contracts |
| `validation/` | Qualification state, scorecards, acceptance evidence |
| `experiments/` | Reproducible experiment methodology, results, adoption/rejection records |
| `../backup/reference/` | Historical/pre-v2 material only; non-authoritative |

Do not copy a current PR number, branch head, run ID, or commit SHA into multiple overview documents unless there is a specific audit/reproducibility reason. Link to the owning record instead.

## Current v2 architecture

Start with:

- [`v2/ANALYSIS_ARCHITECTURE_2026.md`](v2/ANALYSIS_ARCHITECTURE_2026.md) — narrative-analysis architecture.
- [`v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`](v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md) — local literary-NLP provider boundary.

Use `PROJECT.md` to determine which architecture documents are active for the current phase.

## Phase contracts

Active Phase 3 entry points:

- [`phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`](phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md)
- [`phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`](phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md)

Phase files define intended scope and exit criteria. They should not be treated as proof that a capability has shipped; check `PROJECT.md` and validation records for actual current state.

## Validation and scorecards

Primary Phase 3 component ledger:

- [`validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](validation/PHASE_V2_3_COMPONENT_SCORECARD.md)

Validation documents own measured state and qualification conclusions. They should state whether a result is:

- public regression evidence;
- protected/private product qualification;
- a coverage/failure-mode diagnostic;
- correctness evidence;
- a challenger comparison;
- or an adoption/rejection decision.

## Experiment records

`experiments/` contains reproducible measurement records for areas such as:

- whole-book analysis;
- character identity;
- scene segmentation;
- quote and speaker attribution;
- event triggers and participants;
- BookNLP subprocess/persistent-runtime experiments;
- relationship evidence;
- narrative timeline evidence;
- character life-state candidate evidence.

Experiment success does **not** imply production adoption. The relevant decision/scorecard owns that conclusion.

## Historical material

Pre-v2/runtime-reference material is retained for evidence and migration context only. Historical documents and code must not override active v2 contracts, decisions, or validation records.

When an old technique is re-adopted, it should enter v2 through a current contract and current qualification path rather than by treating the historical implementation as authoritative.

## Documentation maintenance rule

Before closing a phase or materially changing an adopted capability:

1. update the owning decision/contract if necessary;
2. update the relevant validation/experiment record;
3. update `PROJECT.md` if high-level current state changed;
4. update the root README only when the public/stable description changed;
5. avoid copying volatile implementation checkpoints into this index.

The goal is a documentation graph with clear ownership—not several competing versions of “current status.”
