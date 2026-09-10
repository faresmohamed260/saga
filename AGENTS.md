# S.A.G.A. AI Development Instructions

S.A.G.A. is developed with AI assistance across independent sessions and tools. The `faresmohamed260/saga` repository is the persistent and primary source of truth.

## Mandatory Startup

Before substantial work, read in this order:

1. `PROJECT.md`
2. `docs/README.md`
3. `docs/DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. the v2 subsystem documentation relevant to the task

Verify the repository, active branch, and exact HEAD before writes. Do not infer current implementation state from chat history when GitHub can establish it.

## Current Architecture Boundary

The owner authorized a fresh **S.A.G.A. v2** rebuild on 2026-09-11.

The product goals remain, but the previous Python/nine-stage runtime architecture is no longer the active architecture.

### Active v2 surfaces

- `apps/web/` — Next.js web product and initial backend/API layer
- `docs/v2/` — current v2 architecture/subsystem contracts
- `docs/phases/PHASE_V2_*.md` — active/progressive v2 phase contracts
- v2-specific GitHub Actions workflows
- future v2 Supabase/schema and agent-runtime paths explicitly adopted by a v2 phase

### v1 historical/reference surfaces

Until they are removed or archived, the pre-v2 Python/runtime surfaces are historical reference material, including:

- `packages/`
- `integrations/`
- `apps/dashboard_api/`
- `apps/dashboard_pro/`
- `deploy/production/`
- pre-v2 migration/runtime/qualification scripts and tests
- pre-v2 runtime/qualification/recovery documentation

Do not add new v2 functionality to v1 surfaces. Do not import v1 implementation into `apps/web`. Reuse a v1 algorithm, schema idea, evaluation method, prompt, or provider technique only by implementing it deliberately behind a v2-owned contract.

`backup/reference/` remains historical/inert.

The separate `faresmohamed260/renderlab` repository remains a different product. S.A.G.A. may adopt proven engineering conventions or the same technology family, but must not copy RenderLab implementation state, product routes, database ownership, credentials, or deployment assumptions as if they were S.A.G.A. facts.

## v2 Product/Engineering Direction

The rebuild order is:

1. web frontend and backend product foundation;
2. auth, relational application data, storage, jobs, deployment, and UX contracts;
3. agentic AI architecture and execution layer;
4. progressive restoration of S.A.G.A. analysis/canon/generation/media capabilities.

Do not start broad agent/LLM implementation while the active phase says the web/backend foundation is incomplete.

## Adopted Web Stack

Unless a later accepted decision changes it, v2 uses:

- Next.js + React + TypeScript
- Vercel
- Supabase Postgres/Auth/Realtime
- Tailwind CSS and maintained component primitives
- Motion for intentional interaction/animation
- Cloudflare for DNS/CDN/security where useful
- Backblaze B2 for S.A.G.A. object storage
- GitHub Actions for deterministic validation and bounded infrastructure operations

Prefer the mature engineering patterns demonstrated by the Studio/RenderLab lineage: feature-oriented application organization, explicit server boundaries, environment validation, structural tests, typechecking, maintained UI primitives, and remote CI. Do not mechanically copy RenderLab code.

## Storage Rules

S.A.G.A. v2 does not use the existing shared Cloudflare R2 allocation.

Backblaze B2 is accessed through a v2-owned provider-neutral storage contract. Domain/features must not instantiate AWS/B2 SDK clients directly.

Bootstrap repository secrets currently use these names:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print, commit, return, or artifact-upload their values.

The master key is for bounded account/bootstrap operations only. It is not S3-compatible and must not become the normal web application's storage credential. Runtime B2 access will use a later bucket-scoped application key and explicit S3 endpoint/bucket configuration.

Structured domain/application state belongs in Supabase. Large binary/object payloads belong in B2. Do not turn object storage into an implicit database.

## Source-of-Truth Hierarchy

1. current S.A.G.A. v2 repository code and authoritative v2 documentation;
2. repository history/v1 code for historical evidence and requirements discovery;
3. ChatGPT Project context for supplementary continuity and owner intent;
4. external documentation/research as evidence;
5. current chat as temporary context.

When the owner explicitly changes product direction, update the repository contract rather than continuing an obsolete phase merely because it was previously active.

## State Classification

Use these labels precisely:

- **Implemented** — code exists in the active v2 path.
- **Validated** — implementation passed the v2-defined validation for the claim.
- **Experimental** — implemented for evaluation, not adopted default.
- **Proposed** — planned but not implemented.
- **Research-backed candidate** — external/historical evidence supports evaluation but v2 has not adopted it.
- **Deprecated/Historical** — preserved for evidence/reference, not active contract.

A working v1 feature is not automatically an implemented v2 feature.

## Architecture Discipline

For each new v2 capability identify:

- owning application/domain boundary;
- public input/output contract;
- persistence owner;
- storage owner when binary artifacts are involved;
- authorization boundary;
- failure/retry semantics;
- UI state and observability needs;
- validation required before calling it complete.

Keep SDK/provider code at infrastructure boundaries. UI/features should depend on S.A.G.A.-owned interfaces, not vendor clients.

Prefer deterministic code for schemas, validation, state transitions, authorization, identifiers, job lifecycle, evidence/provenance, and orchestration invariants. Use LLMs/models later for bounded inference/judgment, not hidden application glue.

## UI/UX Discipline

The main site is a product, not a debugging dashboard.

- establish reusable design tokens/primitives before one-off styling spreads;
- maintain accessibility and responsive behavior;
- prefer intentional motion over gratuitous animation;
- do not silently drift layouts between sessions;
- encode important visual/product conventions in repository tests/docs where practical;
- use feature-oriented components rather than giant page files;
- design the user workflow around stories/projects/canon/media, not around internal AI pipeline stages.

## Research and v1 Reuse

S.A.G.A. has substantial prior research and implementation evidence. Treat it as an input to v2, not a constraint.

When reusing an old idea:

1. identify the v2 capability/failure mode it serves;
2. inspect v1 evidence/implementation;
3. define the v2 contract first;
4. port only the useful logic/idea;
5. add v2-native tests;
6. record the decision if it changes architecture.

Do not bulk-port legacy code to accelerate apparent progress.

## Progressive Phase Planning

Fully specify only the immediate active phase. Keep later phases at roadmap level until current evidence is stable.

Before implementing a phase:

1. verify exact repository state;
2. state goal/user value;
3. define in-scope/out-of-scope work;
4. define affected data/provider/security boundaries;
5. define validation and exit criteria.

Before finishing a phase:

1. verify the implementation and exact head;
2. inspect/run required CI;
3. update `PROJECT.md`, decisions, and the phase contract;
4. record blockers and the next concrete phase.

## GitHub / Remote-First Convention

GitHub is the source of truth. Prefer repository operations and hosted CI over undocumented scratch/local state.

- use focused branches/PRs;
- do not merge stale CI evidence after a branch moves;
- do not expose secrets in workflow commands/logs/artifacts;
- live infrastructure mutations must be bounded and intentional;
- provider-cost operations require explicit authorization when they can incur meaningful usage charges;
- ordinary CI must remain free/non-live where practical.

## v2 Validation Baseline

For the web app, use the current scripts in `apps/web/package.json`. The intended minimum gate is:

```text
cd apps/web
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

A green legacy Python workflow does not validate v2. A v2 PR should have v2-specific CI evidence on its exact final head.

## Documentation Ownership

- current state / active phase / immediate next step -> `PROJECT.md`
- documentation authority/index -> `docs/README.md`
- durable cross-cutting decisions -> `docs/DECISIONS.md`
- current phase scope/evidence -> active `docs/phases/PHASE_V2_*.md`
- v2 subsystem/architecture behavior -> `docs/v2/`
- dated evidence -> `docs/validation/` only when useful

Do not create competing status documents when an authoritative file already owns the information.

## Scope Discipline

Follow the owner's requested scope. The current active rebuild explicitly prioritizes the main site frontend/backend before the agentic AI component.

Do not revive the v1 production qualification/R2 repair path unless the owner explicitly reverses the v2 decision.