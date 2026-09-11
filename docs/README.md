# S.A.G.A. Documentation Index

S.A.G.A. is in an owner-authorized v2 rebuild. This index separates the **active v2 source of truth** from retained **v1 historical/reference material** and from read-only external project references.

## Read First

For substantial current work, read in this order:

1. `../AGENTS.md`
2. `../PROJECT.md`
3. `DECISIONS.md`
4. the current/most-recent v2 phase contract referenced by `PROJECT.md`
5. the relevant document under `v2/`

GitHub is authoritative. Do not reconstruct project state from chat history when the repository can establish it.

## Current Phase State

**S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

Authoritative completion records:

- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md`
- `validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`

Phase 1 established and proved:

- invite-only Supabase Auth + S.A.G.A.-owned admission/role/status state;
- private route and active-admin boundaries;
- real hosted invitation delivery through verified Resend SMTP;
- `/auth/confirm` invitation verification + transactional product claim;
- Set Password + later fresh password sign-in;
- hosted suspension/reactivation behavior;
- Narrative Desk responsive shell and Admin workspace;
- dedicated Supabase/Vercel/B2 foundations;
- manual-only Vercel deployment governance.

There is **no authoritative Phase 2 contract yet**. The next work is to define the next v2 phase before implementing a new agent/LLM runtime.

## Active v2 Governance

- `../AGENTS.md` — mandatory working rules, source-of-truth order, phase discipline, v2/v1 boundary, RenderLab boundary
- `../PROJECT.md` — current hosted reality, completed Phase 1 state, deferred items and immediate next work
- `DECISIONS.md` — durable cross-cutting v2 decisions
- `phases/PHASE_V2_1_CLOSED_DEMO_APP.md` — completed Phase 1 contract and exit evidence
- `operations/VERCEL_DEPLOYMENT_POLICY.md` — manual-only Vercel deployment rule

## Phase Baselines

- Phase 0 web foundation — PR #149, merge `261b75ff2a60dfcada681af6b6c918c1ff5e3366`
- Phase 1 contract/governance — PR #152, merge `55beaccab011a4c5337db86dd88b52f6d48734c4`
- Phase 1B account/access — PR #153, merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- Phase 1C auth/access — PR #156, merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- Phase 1D Narrative Desk — PR #160, merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- Phase 1E deterministic Admin — PR #162, merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- Phase 1 deterministic handoff — PR #163, merge `c274f1d26914edf62e30cfd2ef23222df6a8503f`
- manual-only Vercel deployment policy — PR #173, merge `4c592a5590fdd46ac075a20def4b9d03c169f880`

## Active v2 Architecture / Product Contracts

- `v2/ARCHITECTURE.md` — top-level web-first ownership/deployment boundary
- `v2/FRONTEND_ARCHITECTURE.md` — Next.js route/component/server ownership, state and API direction
- `v2/UI_SYSTEM.md` — S.A.G.A.-specific UI/UX, component sourcing, responsive/accessibility and visual-review rules
- `v2/PHASE_1D_UI_CONCEPT.md` — approved Narrative Desk shell/navigation/composition direction
- `v2/ACCESS_AND_INVITATIONS.md` — closed-demo identity, account access, invitations, admin and email-delivery contract

## Active v2 Code / Operations

- `../apps/web/` — active Next.js web product
- `../apps/web/src/components/shell/` — Narrative Desk shell and responsive navigation
- `../apps/web/src/features/auth/` — invitation/password/sign-in/sign-out product surfaces
- `../apps/web/src/features/admin/` — Admin server actions and workspace
- `../apps/web/src/server/account/` — fresh Auth identity and S.A.G.A. account/access resolution
- `../apps/web/src/server/admin/` — active-admin authorization and bounded Admin operations
- `../apps/web/src/server/supabase/` — ordinary SSR/server and isolated privileged Supabase boundaries
- `../apps/web/src/server/storage/` — provider-neutral object-storage boundary + B2 implementation
- `../apps/web/supabase/migrations/` — active v2 Supabase migration lineage
- `../apps/web/supabase/tests/` — disposable-Postgres account/access/Admin contracts
- `../config/v2-storage.json` — safe Backblaze B2 metadata
- `../.github/workflows/v2-web-ci.yml` — deterministic web/database CI
- `../.github/workflows/v2-visual-review.yml` — production-build Chromium rendered validation
- `../.github/workflows/v2-b2-bootstrap.yml` — manual-only Backblaze bootstrap/storage smoke workflow

## Phase 1 Validation Evidence

- `validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- `validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- `validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- `validation/PHASE_V2_1E_HOSTED_VERCEL_2026-09-11.md`
- `validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md` — final hosted Auth/email/invitation/access proof; supersedes earlier pending conclusions in the foundation snapshots

Key hosted proof runs:

- access/suspension: `34647243289` — success
- full invitation lifecycle: `34647592382` — success

## Current Hosted Boundary

### Supabase

Dedicated project:

- ref `scmeqnpmhomzcwecjdtu`
- region `eu-central-1`
- public signup disabled
- custom Resend SMTP active
- Auth Site URL currently `https://saga-pi-two.vercel.app`
- future custom-domain redirect allowance includes `https://saga.faresuniform.uk/**`

The existing `AI Studio` Supabase project was not reused or modified.

### Vercel

Dedicated `saga` project uses `apps/web`.

The historical `studio` project was disconnected from S.A.G.A. Git pushes. Git-triggered Preview and Production deployments are disabled. Any Vercel deployment requires fresh explicit owner approval after stating the reason, deployment type, and exact commit/SHA.

### Backblaze B2

The dedicated private S.A.G.A. bucket is validated. A scoped runtime key remains deferred until an active product feature needs object storage.

## Open / Deferred Work

These are not Phase 1 blockers:

- custom domain `saga.faresuniform.uk` — tracked by issue #165;
- scoped B2 runtime credentials when source/object upload becomes active;
- PR #172 (`Expose hosted release identity in health checks`) — parked; Phase 1 proof completed without it. Re-evaluate against current `main` before refresh/closure/merge.

## Next-Phase Boundary

Phase 1 completion allows planning of the next S.A.G.A. intelligence phase, but old v1 runtime documents do not automatically become active architecture.

Before implementation:

1. select the next user-visible intelligence capability;
2. inspect relevant v1 requirements/algorithms as historical input;
3. translate reused concepts into v2-owned data/job/provider contracts;
4. write an authoritative new phase contract under `phases/`;
5. define deterministic and hosted validation gates;
6. only then implement through normal branch/PR/exact-head CI.

## RenderLab Reference Boundary

`faresmohamed260/renderlab` is a separate product and read-only reference for process/architecture/UI conventions only.

Do not modify RenderLab or copy its product code, page composition, visual identity, routes, schema/table names, data, credentials, storage or deployment state.

S.A.G.A.-owned translations are authoritative:

- `v2/FRONTEND_ARCHITECTURE.md`
- `v2/UI_SYSTEM.md`
- `v2/ACCESS_AND_INVITATIONS.md`

## Historical v1 Material

The following remain useful for requirements discovery, algorithms, evaluation history, provider experiments, and lessons learned, but do **not** define active v2 architecture unless explicitly re-adopted:

- `system_agent_roadmap.md`
- `agent_framework.md`
- `production_orchestration_runtime.md`
- `execution_runtime.md`
- `lineage_runtime.md`
- `observability_runtime.md`
- `analysis_foundation_runtime.md`
- `identity_runtime.md`
- `canon_extraction_runtime.md`
- `character_world_modeling_runtime.md`
- `retrieval_runtime.md`
- `generation_planning_runtime.md`
- `narrative_generation_runtime.md`
- `visual_generation_runtime.md`
- `audiobook_generation_runtime.md`
- `persistence_runtime.md`
- `storage_architecture.md`
- `runtime_secrets.md`
- `modal_runtime.md`
- `deployment_operations.md`
- `production_qualification.md`

The clean pre-v2 boundary is commit `b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`.

## Documentation Maintenance

When v2 changes:

- current state/phase/next step -> `PROJECT.md`
- cross-cutting decision -> `DECISIONS.md`
- phase scope/evidence -> `phases/PHASE_V2_*.md`
- frontend/server ownership -> `v2/FRONTEND_ARCHITECTURE.md`
- UI/UX rules -> `v2/UI_SYSTEM.md`
- account/invitation/auth rules -> `v2/ACCESS_AND_INVITATIONS.md`
- broader deployment/system boundary -> `v2/ARCHITECTURE.md`
- dated validation evidence -> `validation/`

If v1 behavior or an external-project convention is reused, document the new v2 ownership instead of making the old source active again.
