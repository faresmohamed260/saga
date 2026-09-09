# AI Development Instructions

S.A.G.A. is developed with AI assistance across multiple independent sessions and tools. The `faresmohamed260/saga` repository is the persistent and primary source of truth.

## Required Context

Before substantial project work, read in this order:

1. `PROJECT.md`
2. `docs/README.md`
3. `docs/DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. the subsystem/runtime documentation relevant to the requested work

For architecture or end-to-end pipeline work, also read the current relevant versions of:

- `docs/system_agent_roadmap.md`
- `docs/production_orchestration_runtime.md`
- `docs/storage_architecture.md`
- `docs/deployment_operations.md`
- `docs/production_qualification.md`

For identity work, read `docs/identity_runtime.md` and the active experiment/evaluation material referenced by the current phase before changing behavior.

Do not fill unfinished documentation from assumptions. Inspect implementation, CI evidence, and repository history first.

## Source-of-Truth Hierarchy

1. Current S.A.G.A. repository code and authoritative repository documentation
2. ChatGPT Project context for supplementary continuity and user intent
3. External research, papers, model cards, benchmarks, and other repositories as evidence only
4. Current chat session as temporary working context

If older Project/chat context conflicts with current repository state, follow the repository unless the user explicitly changes the decision.

External projects are not S.A.G.A. specifications. Do not transfer another project's implementation state, architecture, UI, routes, or deployment assumptions into S.A.G.A. merely because a workflow convention is similar.

## State Classification

When describing project state, use these meanings consistently:

- **Implemented** — code exists in the active repository path.
- **Validated** — implementation has passed the repository-defined validation for the claim being made.
- **Experimental** — implementation/configuration exists for evaluation but is not an adopted default.
- **Proposed** — planned or suggested, but not implemented.
- **Research-backed candidate** — external evidence supports evaluation, but S.A.G.A. has not adopted it.
- **Deprecated/Historical** — retained for evidence or reference but not part of the active contract.

Never convert a proposal, research report, old experiment, or successful local run into an implementation/production claim without repository evidence.

## Active vs Historical Code

The active contract-driven architecture is under `packages/`, `integrations/`, `apps/dashboard_api/`, `apps/dashboard_pro/`, `deploy/production/`, `migrations/`, `supabase/`, `scripts/`, and `tests/` as documented by the current project record.

`backup/reference/` is historical reference material. Active code must not depend on it.

`apps/studio/` also exists and has received later repository activity than some S.A.G.A. core documentation. Its long-term ownership/status is being reconciled by the active repository-recovery phase. Do not delete it, treat it as the S.A.G.A. core UI, or expand it by default unless the current phase/user request explicitly requires that work.

## Research and Experiment Discipline

S.A.G.A. is research-heavy. Research must become testable project work before it becomes architecture.

For a research-driven change, identify:

1. failure mode or capability gap;
2. hypothesis;
3. smallest useful implementation/experiment;
4. dataset/input and baseline;
5. metrics and qualitative checks;
6. acceptance/rejection criteria;
7. runtime/resource impact where relevant;
8. result and conclusion;
9. documentation/decision update if adopted.

Preserve the current implementation as a baseline when practical. Prefer controlled comparisons over intuition-driven rewrites.

## Evaluation Integrity

Implementation is not complete merely because code runs.

For measurable NLP, identity, retrieval, generation, visual, audio, orchestration, and reliability changes, use the repository's established tests/qualification paths and record enough evidence to reproduce the conclusion.

Do not compare metrics produced under materially different datasets, subsets, adapters, preprocessing, model versions, or scoring rules as if they were directly comparable.

Do not optimize around a handful of known books or examples. Fix the general failure class, rerun the relevant benchmark, inspect regressions, and add regression coverage when appropriate.

## Pipeline and Contract Integrity

S.A.G.A. is a multi-stage system. Before changing a component, identify its inputs, outputs, ownership boundary, persistence contract, and downstream consumers.

The analysis side produces durable canon memory. Generation-side systems should consume canon/retrieval artifacts rather than reconstructing canon ad hoc when those artifacts exist.

Do not bypass reusable runtime packages with ad hoc provider/database integrations when an active package owns that boundary.

Prefer deterministic code for schema ownership, validation, state transitions, evidence accounting, and orchestration invariants. Use models/LLMs for bounded inference or judgment rather than hidden system glue.

## Identity Resolution Rule

Identity quality is upstream of downstream canon quality. Keep mention/cluster contamination handling inside the identity subsystem unless the active architecture explicitly changes that ownership.

For identity changes:

- distinguish mention proposal, attachment/coreference, canonical creation, alias review, and downstream consumption;
- evaluate false merges, fragmentation, false canonical creation, alias contamination, and recall/coverage rather than one aggregate score alone;
- do not add book-specific lexical patches as a default response to isolated failures;
- preserve evidence/provenance for accepted and rejected identity decisions where the contracts support it;
- treat external proposals such as alternative span proposal, type gating, quote attribution, cache/quarantine policies, or different coreference models as research-backed candidates until S.A.G.A. validates and adopts them.

## Model, Provider, Dataset, and Dependency Changes

Do not replace a model, parser, coreference system, provider, storage layer, dataset, generation model, or major library solely because a newer option exists.

Consider task evidence, compatibility, cost, latency, VRAM/RAM, deployment constraints, licensing, reproducibility, determinism, maintenance, and downstream contracts.

Dataset version/split/adapter/preprocessing/scoring changes must be explicit because they can invalidate metric comparability.

## Progressive Phase Planning

For substantial recovery or multi-phase development cycles, keep a roadmap-level direction but fully specify only the immediate next phase.

Before implementation of a phase:

1. re-establish current repository and dependency reality;
2. define goal and user/system value;
3. record verified starting state;
4. define in-scope and explicit out-of-scope work;
5. identify affected contracts/data/providers/security boundaries;
6. define validation and exit criteria;
7. merge/update the phase contract before broad implementation when practical.

When a phase completes, update the project record from verified reality before expanding the next phase. Planning detail is not evidence of completion.

## Session Continuity

At the beginning of substantial work:

1. verify repository, branch, and exact HEAD;
2. read required project documentation;
3. inspect relevant source and CI/qualification evidence;
4. identify active phase, completed work, open work, and constraints;
5. distinguish latest repository HEAD from latest validated application/runtime/qualification head;
6. continue from verified repository state.

Before finishing substantial work:

1. verify the resulting implementation state;
2. run or inspect required validation where possible;
3. update durable decisions/status/phase documentation;
4. record unresolved blockers and the next concrete step.

A completely new session should be able to continue correctly from the repository without needing the previous conversation.

## Documentation Updates

Durable state must be recorded in the appropriate existing source of truth.

- project baseline / active phase / next step -> `PROJECT.md`
- documentation map and authority -> `docs/README.md`
- durable architecture/product/process decisions -> `docs/DECISIONS.md`
- phase scope and acceptance evidence -> active file under `docs/phases/`
- subsystem behavior -> existing subsystem runtime document
- production qualification evidence -> `docs/production_qualification.md`

Update an existing authoritative document instead of creating a competing one.

Do not preserve stale statements merely because they were once true. If documentation and implementation disagree, investigate and correct the authoritative record or mark the discrepancy explicitly unresolved.

## Scope Discipline

Follow the user's requested scope precisely.

Do not redesign, refactor, retrain, migrate, deploy, replace providers/models, merge unrelated PRs, or expand scope merely because doing so seems useful.

Do not undo unfamiliar work. Inspect history and intent first.

Deployment or production mutation always remains a separate explicit operation unless the user specifically requests it.

## Validation

Use the validation required by the affected surface. At minimum, relevant work should consider:

- Python lock/install consistency: `uv sync --frozen --extra dev`
- backend tests: `uv run pytest -q`
- dashboard: `cd apps/dashboard_pro`, `npm ci`, `npm test -- --run`, `npm run build`
- architecture-boundary and migration/release gates in GitHub Actions
- real-provider/live qualification only when the phase requires it and credentials/environment are available

A green unrelated workflow does not prove the affected S.A.G.A. subsystem is valid.
