# S.A.G.A. Documentation Index

This file is the navigation layer for S.A.G.A. documentation. It intentionally does not duplicate volatile branch, PR, workflow, or commit state.

For the current high-level project handoff and phase status, read [`../PROJECT.md`](../PROJECT.md). Git history is authoritative for exact merge state.

## Read first

For substantial current work, use this order:

1. [`../AGENTS.md`](../AGENTS.md) — repository/AI development instructions.
2. [`../PROJECT.md`](../PROJECT.md) — current project handoff and phase status.
3. [`DECISIONS.md`](DECISIONS.md) — durable architecture/product decisions.
4. [`phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`](phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md) — active implementation contract.
5. [`v3/README.md`](v3/README.md) — v3 reboot documentation entry point.
6. The relevant v3 architecture/IR/evaluation contract.
7. [`validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](validation/PHASE_V2_3_COMPONENT_SCORECARD.md) when comparing against the frozen v2 baseline.
8. Detailed evidence under `experiments/` when a decision depends on measurements.

## Documentation ownership

| Source | Owns |
| --- | --- |
| `../README.md` | Public project overview, positioning, quick start and stable architecture summary |
| `../PROJECT.md` | Current high-level phase/capability handoff |
| `DECISIONS.md` | Durable adopted decisions and constraints |
| `phases/` | Phase implementation contracts, scope and exit criteria |
| `v3/` | Active Narrative Compiler architecture, IR, ontology, model, provenance and migration contracts |
| `v2/` | Frozen/current-operational v2 architecture and reference contracts during migration |
| `validation/` | Qualification state, scorecards and acceptance evidence |
| `experiments/` | Reproducible experiment methodology/results/adoption records |
| `../backup/reference/` | Historical/pre-v2 reference material only |

## Active v3 architecture

Start with:

- [`v3/README.md`](v3/README.md) — reboot package status and V3.0 scope.
- [`v3/ARCHITECTURE.md`](v3/ARCHITECTURE.md) — target compiler architecture.
- [`v3/NARRATIVE_IR.md`](v3/NARRATIVE_IR.md) — canonical semantic intermediate representation.
- [`v3/ONTOLOGY.md`](v3/ONTOLOGY.md) — semantic boundaries and definitions.
- [`v3/PIPELINE_DAG.md`](v3/PIPELINE_DAG.md) — stage dependencies, caching and invalidation.
- [`v3/PROVENANCE_SPEC.md`](v3/PROVENANCE_SPEC.md) — evidence/run/artifact provenance.
- [`v3/EVALUATION.md`](v3/EVALUATION.md) — v2-v3 evaluation and promotion rules.
- [`v3/MODEL_STRATEGY.md`](v3/MODEL_STRATEGY.md) — model-role strategy and challenger policy.
- [`v3/MODEL_LICENSES.md`](v3/MODEL_LICENSES.md) — initial license ledger.
- [`v3/DATABASE_SCHEMA.md`](v3/DATABASE_SCHEMA.md) — canonical persistence draft.
- [`v3/MIGRATION_V2_TO_V3.md`](v3/MIGRATION_V2_TO_V3.md) — shadow/migration plan.
- [`v3/adr/0001-narrative-compiler.md`](v3/adr/0001-narrative-compiler.md) — architecture decision record.

## Active phase contract

V3.0:

- [`phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`](phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md)

V3.0 implements only the foundation:

```text
source compiler
  -> semantic lexer
  -> global character linker
  -> Narrative IR
  -> v2/v3 benchmark
```

Phase files define intended scope and exit criteria; they are not proof that a capability has shipped. Check `PROJECT.md` and validation records for actual status.

## Frozen v2 baseline/reference

The v2 analysis runtime remains operational/reference material during shadow migration. Its architecture documents are not the accepted long-term semantic target.

Key references:

- [`v2/ANALYSIS_ARCHITECTURE_2026.md`](v2/ANALYSIS_ARCHITECTURE_2026.md)
- [`v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md`](v2/LOCAL_LITERARY_PROVIDER_PROTOCOL.md)
- [`phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md`](phases/PHASE_V2_3_LOCAL_FIRST_NARRATIVE_ANALYSIS.md)
- [`phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md`](phases/PHASE_V2_3_PRIMARY_EVALUATION_CORPUS.md)

Use these to preserve measurements, behavior and migration evidence—not to silently override the active v3 contract.

## Validation and scorecards

The primary frozen v2 component ledger is:

- [`validation/PHASE_V2_3_COMPONENT_SCORECARD.md`](validation/PHASE_V2_3_COMPONENT_SCORECARD.md)

V3 qualification must distinguish:

- public regression evidence;
- private/protected product qualification;
- coverage/failure-mode diagnostics;
- correctness evidence;
- challenger comparison;
- production adoption/rejection.

External leaderboard/model-card results may justify running a challenger; they never constitute S.A.G.A. adoption evidence by themselves.

## Experiment records

`experiments/` contains reproducible measurement records for areas such as whole-book analysis, identity, scenes, dialogue/speakers, events, BookNLP runtime behavior, relationships, timeline evidence and state-change candidates.

Experiment success does not imply production adoption. The relevant decision/scorecard owns that conclusion.

## Historical material

Pre-v2 material remains historical/reference-only. The v2 semantic architecture is now also a frozen operational/comparison baseline where it conflicts with the accepted v3 Narrative Compiler direction.

When a historical technique is useful, re-adopt it through a current v3 contract and current qualification path rather than treating old implementation state as authoritative.

## Documentation maintenance rule

Before closing a phase or materially changing an adopted capability:

1. update the owning decision/phase contract if necessary;
2. update the relevant validation/experiment record;
3. update `PROJECT.md` when high-level state changes;
4. update the root README only when the public/stable product description changes;
5. keep exact volatile run/commit details in their owning evidence record rather than duplicating them broadly.

The goal is a documentation graph with clear ownership—not competing versions of current state.