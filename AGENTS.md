# S.A.G.A. AI Development Instructions

S.A.G.A. is developed with AI assistance across independent sessions and tools. The `faresmohamed260/saga` repository is the persistent and primary source of truth.

## Mandatory Startup

Before substantial work, read in this order:

1. `PROJECT.md`
2. `docs/README.md`
3. `docs/DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. relevant `docs/v2/` subsystem documentation

For frontend/UI work also read:

- `docs/v2/UI_SYSTEM.md`
- `docs/v2/DESIGN_WORKFLOW.md`

Verify repository, active branch, and exact remote HEAD before writes. Do not infer current implementation state from chat history when GitHub can establish it.

## Current Architecture Boundary

The owner authorized a fresh **S.A.G.A. v2** rebuild on 2026-09-11.

The product goals remain, but the previous Python/nine-stage runtime is no longer the active architecture.

### Active v2 surfaces

- `apps/web/` — Next.js web product and request-bounded backend/API layer
- `docs/v2/` — active v2 architecture/UI/subsystem contracts
- `docs/phases/PHASE_V2_*.md` — progressive v2 phase contracts
- v2-specific GitHub Actions workflows
- v2-owned schema/migrations explicitly adopted by the active phase

### v1 historical/reference surfaces

Until removed/archived, pre-v2 runtime surfaces are historical evidence only, including:

- `packages/`
- `integrations/`
- `apps/dashboard_api/`
- `apps/dashboard_pro/`
- `deploy/production/`
- pre-v2 migration/runtime/qualification scripts and tests
- pre-v2 runtime/qualification/recovery docs
- `backup/reference/`

Do not add new v2 functionality to v1 surfaces. Do not import v1 implementation into `apps/web`. Reuse old ideas only by deliberately implementing them behind v2-owned contracts.

## RenderLab Is Read-Only Reference

`faresmohamed260/renderlab` is a different project.

When relevant, inspect it **read-only** for:

- project/repository setup conventions;
- frontend/server ownership patterns;
- Supabase/Auth/admin security lessons;
- maintained component sourcing;
- UI/design-system governance;
- responsive/rendered validation discipline;
- progressive phase planning.

Never modify RenderLab as part of S.A.G.A. work.

Do not copy or share:

- RenderLab routes or product information architecture;
- schema/table names or database ownership;
- R2/storage resources or credentials;
- deployment state;
- brand/visual identity;
- product-specific components or media/generation state;
- implementation wholesale.

If a RenderLab pattern is useful, express the underlying principle in a S.A.G.A.-owned contract and implement it independently.

## Closed-Demo Access Model

S.A.G.A. v2 is a **closed demo**.

Hard rules:

- no public self-service sign-up;
- private application access requires a verified account;
- admission is invitation-only;
- admins create invitations for email addresses;
- invitation emails are sent through a server-only provider/Auth-admin boundary;
- Supabase Auth identity does not by itself grant S.A.G.A. access;
- S.A.G.A. owns separate admission state;
- only active admitted users enter private application routes;
- unknown/pending/suspended/unverifiable identities fail closed;
- browser code never receives Supabase service-role/Auth-admin capability;
- authorization roles come from S.A.G.A. server-owned access records, never browser/user metadata;
- invitation/public responses must not become email/account enumeration oracles.

Production invitation/recovery email readiness requires verified Site URL/redirects/templates and production-capable SMTP or equivalent email hook. Do not claim live email readiness from code alone.

## v2 Product/Engineering Direction

Development order:

1. web frontend/backend product foundation;
2. auth, relational data, storage, jobs, deployment, UX contracts;
3. agentic AI architecture/execution layer;
4. progressive restoration of S.A.G.A. analysis/canon/generation/media capabilities.

Do not start broad agent/LLM implementation while the active phase says the web/backend foundation is incomplete.

## Adopted Web Stack

Unless a later accepted decision changes it:

- Next.js + React + TypeScript
- Vercel
- Supabase Postgres/Auth/Realtime
- Tailwind CSS + maintained accessible component primitives
- Motion for purposeful interaction/continuity
- Cloudflare for DNS/CDN/security where useful
- Backblaze B2 for S.A.G.A. object storage
- GitHub Actions for deterministic validation and bounded infrastructure operations

Use Server Components by default. Add Client Components only where browser interaction/local state is actually needed.

Keep provider/admin SDKs at server/infrastructure boundaries.

## Storage Rules

S.A.G.A. v2 does not use the existing shared Cloudflare R2 allocation.

Backblaze B2 is behind a v2-owned provider-neutral `ObjectStorage` boundary. Features/domain code must not construct AWS/B2 clients directly.

Bootstrap repository secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print, commit, return, or artifact-upload their values.

The master key is bounded bootstrap/admin capability only. Normal runtime access must use a bucket-scoped application key.

Supabase owns structured application/domain state. B2 owns large binary/object payloads.

## Source-of-Truth Hierarchy

1. current S.A.G.A. v2 repository code and authoritative v2 docs;
2. S.A.G.A. history/v1 code for historical evidence and requirements discovery;
3. read-only RenderLab reference when the active task explicitly benefits from its proven setup/process patterns;
4. ChatGPT Project context for supplementary continuity/owner intent;
5. external docs/research as evidence;
6. current chat as temporary context.

Never let RenderLab state override S.A.G.A. repository state.

## State Classification

- **Implemented** — code exists in active v2 path.
- **Validated** — implementation passed the v2-defined validation for the claim.
- **Experimental** — implemented for evaluation, not adopted default.
- **Proposed** — planned but not implemented.
- **Research-backed candidate** — evidence supports evaluation but v2 has not adopted it.
- **Deprecated/Historical** — retained for evidence/reference, not active contract.

A working v1 or RenderLab feature is not automatically an implemented S.A.G.A. feature.

## Architecture Discipline

For every new v2 capability identify:

- owning application/domain boundary;
- public input/output contract;
- persistence owner;
- object-storage owner when needed;
- authorization boundary;
- failure/retry semantics;
- UI state/observability needs;
- deterministic validation required before completion.

Prefer deterministic code for schemas, validation, identifiers, state transitions, authorization, evidence/provenance, and job lifecycle. LLMs/models later perform bounded inference/judgment, not hidden application glue.

## UI/UX Discipline

The main site is a product, not a debugging dashboard.

Read and obey `docs/v2/UI_SYSTEM.md` and `docs/v2/DESIGN_WORKFLOW.md`.

Baseline rules:

- story/project/canon/media concepts drive navigation, not internal pipeline stages;
- simple by default, powerful when needed;
- semantic design tokens before one-off visual values;
- maintained accessible primitives before custom generic controls;
- feature components compose shared primitives rather than hand-styling the same mechanics repeatedly;
- use spacing/alignment/tonal hierarchy before nested card stacks;
- deliberate motion must communicate continuity/state and support reduced motion;
- desktop and narrow/mobile are designed together;
- rendered responsive review is separate from build success;
- ordinary feature work stays in Integration Mode; redesign only when the owner explicitly asks to reopen a surface.

### Maintained primitive policy

Before building a generic visible control/mechanic, search:

1. existing S.A.G.A. component;
2. existing S.A.G.A. primitive;
3. shadcn/ui/Radix-compatible maintained primitive;
4. Motion/maintained motion source when appropriate;
5. another production-suitable maintained source after accessibility/license/performance review;
6. custom generic mechanic only with a documented reason.

Native hidden/file inputs may remain platform plumbing.

## Auth / Server-Client Discipline

- root/proxy/session-refresh logic is not product authorization policy;
- private application authorization uses fresh server-verified identity;
- product admission/role/status comes from S.A.G.A.-owned server records;
- service-role/Auth Admin clients are server-only;
- ordinary browser code uses public Supabase configuration only;
- private queries/mutations are account/owner scoped;
- admin routes reverify identity and active admin status server-side;
- avoid a global client auth/admin store unless multiple real features prove it necessary.

## Research and Reuse

When reusing a v1 or RenderLab idea:

1. identify the v2 capability/failure mode it serves;
2. inspect the evidence/implementation;
3. define the S.A.G.A. v2 contract first;
4. implement only the useful principle/logic under S.A.G.A. ownership;
5. add v2-native tests;
6. record the decision when it changes architecture.

Do not bulk-port legacy or RenderLab code to accelerate apparent progress.

## Progressive Phase Planning

Fully specify only the immediate active phase. Keep later phases at roadmap level until current evidence is stable.

Before implementation:

1. verify exact repository state;
2. state goal/user value;
3. define in/out of scope;
4. define data/provider/security boundaries;
5. define validation/exit criteria.

Before phase completion:

1. verify implementation and exact head;
2. inspect/run required CI;
3. perform rendered responsive review where UI changed;
4. update `PROJECT.md`, decisions, and phase contract;
5. record blockers and next concrete phase.

## GitHub / Remote-First Convention

GitHub is source of truth. Prefer repository operations and hosted CI over undocumented local state.

- use focused branches/PRs;
- do not merge stale CI evidence after branch movement;
- do not expose secrets in workflow logs/artifacts;
- live infrastructure mutations must be bounded and intentional;
- provider-cost operations require explicit authorization when they may incur meaningful usage charges;
- ordinary CI remains free/non-live where practical.

## v2 Validation Baseline

```text
cd apps/web
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

A green legacy Python workflow does not validate v2. A v2 PR needs v2-specific exact-head evidence.

UI changes also require actual rendered desktop/narrow review appropriate to the changed surface.

## Documentation Ownership

- current state / active phase / immediate next step -> `PROJECT.md`
- documentation authority/index -> `docs/README.md`
- durable cross-cutting decisions -> `docs/DECISIONS.md`
- current phase scope/evidence -> active `docs/phases/PHASE_V2_*.md`
- v2 subsystem/architecture behavior -> `docs/v2/`
- dated evidence -> `docs/validation/` only when useful

Do not create competing status docs when an authoritative file already owns the information.

## Scope Discipline

Follow the owner's requested scope. The current rebuild prioritizes the main site frontend/backend and closed-demo account/invitation foundation before the agentic AI subsystem.

Do not revive v1 production qualification/R2 repair unless the owner explicitly reverses the v2 direction.
