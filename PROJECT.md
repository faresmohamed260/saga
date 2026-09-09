# S.A.G.A. Project

S.A.G.A. (Story Analysis, Generation, and Archives) analyzes source books into evidence-backed canon, generates grounded narrative and multimedia outputs, and packages auditable release artifacts.

This file is the short current-state handoff for humans and AI sessions. Detailed subsystem behavior belongs in the existing documents indexed by `docs/README.md`.

## Product / System Direction

The active S.A.G.A. architecture is contract-driven and modular rather than a monolithic book-processing application.

Primary active surfaces documented by the repository are:

- `packages/` — reusable runtimes for agents, reasoning, retrieval, persistence, execution, identity, generation, observability, lineage, qualification, and deployment;
- `integrations/` — provider implementations, including ComfyUI and XCore/Modal integration;
- `apps/dashboard_api/` — stateless FastAPI control/query surface;
- `apps/dashboard_pro/` — operator dashboard;
- `deploy/production/` — production process/container topology;
- `migrations/` and `supabase/` — persistence/schema assets;
- `tests/` and `scripts/` — automated validation and bounded operational entrypoints.

`backup/reference/` is inert historical reference material and must not become an active dependency.

`apps/studio/` remains present and has later repository activity than several S.A.G.A. core status documents. Its final status relative to the S.A.G.A. core is intentionally unresolved until the active recovery phase audits it. Do not silently classify, delete, or expand it.

## Core Pipeline

The repository currently documents a nine-stage production path:

1. source ingestion and analysis foundation;
2. identity resolution;
3. canon extraction;
4. character/world modeling;
5. generation planning;
6. narrative generation and semantic support;
7. visual generation and image QA;
8. audiobook synthesis and transcription QA;
9. EPUB, manifest, lineage, and qualification reporting.

Generation-side systems are expected to consume persisted canon/retrieval artifacts rather than repeatedly reconstructing canon from raw source text.

## Stack

### Python/runtime

- Python `>=3.10`
- package version currently declared as `0.2.0rc20`
- `uv`-locked Python dependency workflow
- FastAPI
- LangGraph
- PostgreSQL/Supabase + pgvector/object storage through persistence contracts
- Alembic migrations
- provider integrations for reasoning, identity, visual generation, audio, and external compute

### Operator UI

- React/Vite dashboard under `apps/dashboard_pro/`

## Current Verified Repository Baseline — 2026-09-10

Repository audit starting point:

- default branch: `main`;
- audited `main` HEAD: `1d1fa6e9bb86feede9c9f5b89eec828eb15a2050`;
- that commit is a merge of PR #131, `studio/mobile-button-input-cleanup`, dated 2026-08-26;
- the latest observed `main` GitHub Actions run for that head includes successful `Studio CI` and `Required Check Compatibility` workflows;
- Vercel status for that exact head is successful for the Studio deployment surface;
- open PR #132 is additional Studio/Qwen UI work and is not part of the S.A.G.A. recovery/governance change.

This does **not** establish that the complete S.A.G.A. core pipeline is currently production-ready.

## Last Recorded End-to-End S.A.G.A. Qualification

`docs/production_qualification.md` records an accepted real-book run from 2026-08-09 using `Once Upon a Broken Heart.epub` through all nine pipeline stages.

The same record explicitly states that the run was **not promotable** because its source worktree was not a clean committed CI revision and reported 574 pending worktree paths at qualification time.

Therefore:

- the run is valuable behavioral/qualification evidence;
- it is not proof that current `main` is a clean, reproducible, promotable S.A.G.A. release;
- Phase 0 must bind current claims to clean committed source and current CI before production readiness can be asserted.

## Documentation Consistency Findings

The 2026-09-10 audit found several state layers that are individually useful but no longer form a reliable current handoff without reconciliation:

- `docs/system_agent_roadmap.md` describes most production slices as built and says the immediate next step is to merge a stabilization PR, yet `main` has since advanced through later Studio work;
- `docs/architecture_hardening_audit.md` is an earlier architecture audit that still says the next step is rebuilding main agents, while the later roadmap says those agent groups were built;
- `docs/production_qualification.md` contains strong real-book evidence but explicitly lacks clean promotable source provenance;
- the repository contains both S.A.G.A. operator surfaces and `apps/studio/`, while the root README only lists the former as primary architecture surfaces.

Until Phase 0 reconciles these items, use this file plus the active phase contract as the current handoff and treat older “next step” statements as dated evidence rather than instructions.

## Active Phase

**Phase 0 — Repository Baseline Recovery & Requalification**

Contract: `docs/phases/PHASE_0_REPOSITORY_BASELINE_RECOVERY.md`

Status: **ACTIVE / GOVERNANCE BASELINE BEING ESTABLISHED**

The goal is not a redesign. The goal is to establish exactly what current committed S.A.G.A. can build, test, run, and qualify; resolve stale project-state documentation; isolate unrelated surfaces; and produce a clean reproducible baseline from which defects can be fixed in evidence-driven phases.

## Immediate Next Step

After this governance change is reviewed/merged:

1. run an exact-head structural/CI audit of the S.A.G.A. core rather than relying on Studio-only green checks;
2. reconcile existing S.A.G.A. workflow/test coverage against the claims in `README.md`, the roadmap, and qualification docs;
3. classify `apps/studio/`, Studio workflows, open automation issues, and PR #132 without deleting or merging them by assumption;
4. fix only blockers required to obtain a clean committed core baseline;
5. rerun repository-level tests/builds and then a bounded clean-source S.A.G.A. qualification when prerequisites are available;
6. update this file and the Phase 0 contract with exact evidence before declaring recovery complete.

## Development Commands

Python:

```powershell
uv sync --frozen --extra dev
uv run pytest -q
```

Operator dashboard:

```powershell
cd apps\dashboard_pro
npm ci
npm test -- --run
npm run build
```

API after configuring the required persistence environment:

```powershell
uv run saga-runtime-api
```

Production topology configuration is documented in `docs/deployment_operations.md`. Do not deploy merely because local/CI validation passes.

## Working Convention

The repository must remain sufficient for a new session with no conversation history to determine:

- what S.A.G.A. currently is;
- what is active vs historical/experimental;
- what has actually been validated;
- what phase is active;
- what remains blocked or unresolved;
- what exact work should happen next.

Durable project state belongs in the repository, not only in chat history.
