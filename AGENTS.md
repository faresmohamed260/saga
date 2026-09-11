# S.A.G.A. AI Development Instructions

S.A.G.A. is developed with AI assistance across independent sessions and tools. The `faresmohamed260/saga` repository is the persistent and primary source of truth.

## Mandatory Startup

Before substantial work, read in this order:

1. `PROJECT.md`
2. `docs/README.md`
3. `docs/DECISIONS.md`
4. the active phase contract referenced by `PROJECT.md`
5. the v2 subsystem documents relevant to the task

For Phase 1 web/account/UI work, the relevant subsystem documents are:

- `docs/v2/FRONTEND_ARCHITECTURE.md`
- `docs/v2/UI_SYSTEM.md`
- `docs/v2/ACCESS_AND_INVITATIONS.md`
- `docs/v2/ARCHITECTURE.md`

Verify the repository, active branch, and exact HEAD before writes. Do not infer current implementation state from chat history when GitHub can establish it.

## Current Architecture Boundary

The owner authorized a fresh **S.A.G.A. v2** rebuild on 2026-09-11.

The product goals remain, but the previous Python/nine-stage runtime architecture is no longer the active architecture.

### Active v2 surfaces

- `apps/web/` — Next.js web product and request-bounded backend/API layer
- `docs/v2/` — current v2 architecture/subsystem contracts
- `docs/phases/PHASE_V2_*.md` — progressive v2 phase contracts
- v2-specific GitHub Actions workflows
- v2-owned Supabase/schema and future agent-runtime paths explicitly adopted by a v2 phase

### v1 historical/reference surfaces

Until removed or archived, the pre-v2 Python/runtime surfaces are historical reference material, including:

- `packages/`
- `integrations/`
- `apps/dashboard_api/`
- `apps/dashboard_pro/`
- `deploy/production/`
- pre-v2 migration/runtime/qualification scripts and tests
- pre-v2 runtime/qualification/recovery documentation

Do not add new v2 functionality to v1 surfaces. Do not import v1 implementation into `apps/web`. Reuse an old algorithm, schema idea, evaluation method, prompt, or provider technique only by implementing it deliberately behind a v2-owned contract.

`backup/reference/` remains historical/inert.

## RenderLab Is Read-Only Reference Material

`faresmohamed260/renderlab` is a different project.

For S.A.G.A. work it may be **read** to study mature project setup, architecture/process conventions, and UI/UX governance. It must not be modified as part of S.A.G.A. work unless the owner separately requests RenderLab work.

Permitted reference categories include:

- repository-first continuity;
- progressive phase contracts;
- frontend/server/infrastructure ownership boundaries;
- Server Components by default with small client islands;
- maintained accessible UI primitives;
- semantic design tokens;
- responsive/accessibility/reduced-motion discipline;
- closed-beta invitation/access concepts above Supabase Auth;
- remote-first CI, screenshot/render validation, and exact-head review.

Do not copy RenderLab product code, visual identity, page composition, routes, schema/table names, product data, Supabase/R2 credentials, deployments, or assumptions as S.A.G.A. facts. Any borrowed principle must be translated into a S.A.G.A.-owned decision, document, interface, schema, component, or test.

## Closed-Demo Access Rule

S.A.G.A. v2 is a **closed demo**.

- No public self-signup.
- Supabase Auth is the identity/session authority.
- S.A.G.A. tables/services own product access, role, suspension and invitation state.
- Access begins with an admin-created email invitation.
- Private application routes require a fresh server-verified identity plus active S.A.G.A. account state.
- Never authorize from browser-provided user IDs, `user_metadata`, invitation query parameters, or unsigned role claims.
- Invitation/account administration is server-only and active-admin-authorized.
- Service-role/Auth Admin credentials never reach browser code.
- Raw reusable invitation secrets/tokens are not stored in S.A.G.A. application tables.
- Hosted email configuration is an operational dependency; do not claim invitation delivery works until the Supabase Site URL/redirects/templates and SMTP/email hook are verified.

Follow `docs/v2/ACCESS_AND_INVITATIONS.md`.

## v2 Product/Engineering Direction

The rebuild order is:

1. web frontend/backend product foundation;
2. auth, relational application data, storage, jobs, deployment and UX contracts;
3. agentic AI architecture/execution;
4. progressive restoration of analysis/canon/generation/media capabilities.

Do not start broad agent/LLM implementation while the active phase says the web/backend foundation is incomplete.

## Adopted Web Stack

Unless a later accepted decision changes it, v2 uses:

- Next.js + React + TypeScript
- Vercel
- Supabase Postgres/Auth/Realtime
- Tailwind CSS
- maintained accessible primitives, with shadcn/Radix-style ownership as the default foundation where suitable
- Motion for intentional interaction/animation
- Cloudflare for DNS/CDN/security where useful
- Backblaze B2 for S.A.G.A. object storage
- GitHub Actions for deterministic validation and bounded infrastructure operations

Prefer feature-oriented organization, explicit server boundaries, environment validation, structural tests, typechecking, maintained primitives and remote CI. Do not mechanically copy another project.

## Frontend/UI Rules

The main site is a product, not a debugging dashboard.

### Product principle

**Narrative first, complexity on demand.**

- Organize around Library, Projects, Characters, World, Timeline, Canon, Story, Media and Activity rather than internal AI stages.
- Keep implementation/provider terminology out of ordinary product UI unless an advanced/admin surface genuinely needs it.
- Story text, evidence, entities, relationships, timelines and media should dominate over application chrome.
- Progressive disclosure is preferred over showing every future AI/model control up front.

### Component sourcing

Do not repeatedly hand-build conventional visible controls if an accessible maintained implementation is suitable.

Preferred order:

1. existing approved S.A.G.A. component;
2. existing S.A.G.A. primitive;
3. suitable maintained shadcn/Radix primitive;
4. Motion/Motion Primitives or another reviewed maintained source for interaction mechanics;
5. S.A.G.A.-specific composition from approved primitives;
6. custom mechanics only when there is a documented need.

External libraries provide mechanics, not S.A.G.A. visual identity.

### Design discipline

- use semantic design tokens rather than arbitrary visual values once tokens exist;
- avoid default card-grid/admin-dashboard composition for core narrative surfaces;
- avoid card-within-card-within-card nesting;
- preserve responsive behavior from the first implementation slice;
- target WCAG 2.2 AA behavior for normal product UI;
- never require hover for essential actions;
- respect `prefers-reduced-motion` and provide understandable static equivalents;
- use motion to explain hierarchy, continuity or direct manipulation—not as ambient decoration;
- visually important new surfaces require complete concept/review and rendered fidelity validation before being called approved.

Follow `docs/v2/UI_SYSTEM.md`.

## Server / Client Discipline

- Server Components are the default for route composition and server-owned data.
- Client Components exist for interaction that genuinely requires browser state.
- Browser code never receives service-role, Auth Admin or raw object-storage credentials.
- Privileged authorization uses fresh server verification (`auth.getUser()` or equivalent current-session verification), not only local JWT parsing.
- Provider SDKs stay inside server infrastructure boundaries.
- Do not create global client stores for server-owned account, authorization, library or job truth merely for convenience.

Follow `docs/v2/FRONTEND_ARCHITECTURE.md`.

## Storage Rules

S.A.G.A. v2 does not use the existing shared Cloudflare R2 allocation.

Backblaze B2 is accessed through a v2-owned provider-neutral storage contract. Domain/features must not instantiate AWS/B2 SDK clients directly.

Bootstrap repository secrets:

- `SAGA_B2_KEY_ID`
- `SAGA_B2_MASTER_APPLICATION_KEY`

Never print, commit, return or artifact-upload their values.

The master key is for bounded account/bootstrap operations only. Runtime B2 access uses a later bucket-scoped application key and explicit S3 endpoint/bucket configuration.

Structured domain/application state belongs in Supabase. Large binary/object payloads belong in B2.

## Source-of-Truth Hierarchy

1. current S.A.G.A. v2 repository code and authoritative v2 documentation;
2. repository history/v1 code for historical evidence and requirements discovery;
3. approved read-only reference repositories/docs (for example RenderLab) for process/architecture evidence only;
4. ChatGPT Project context for supplementary continuity and owner intent;
5. external documentation/research as evidence;
6. current chat as temporary context.

When the owner changes direction, update repository contracts rather than continuing an obsolete phase.

## State Classification

Use these labels precisely:

- **Implemented** — code exists in the active v2 path.
- **Validated** — implementation passed the v2-defined validation for the claim.
- **Experimental** — implemented for evaluation, not adopted default.
- **Proposed** — planned but not implemented.
- **Research-backed candidate** — external/historical evidence supports evaluation but v2 has not adopted it.
- **Deprecated/Historical** — preserved for evidence/reference, not active contract.

A working v1 or RenderLab feature is not automatically an implemented v2 feature.

## Architecture Discipline

For each new v2 capability identify:

- owning application/domain boundary;
- public input/output contract;
- persistence owner;
- storage owner when binary artifacts are involved;
- authorization boundary;
- failure/retry semantics;
- UI state/observability needs;
- validation required before calling it complete.

Keep SDK/provider code at infrastructure boundaries. UI/features depend on S.A.G.A.-owned interfaces.

Prefer deterministic code for schemas, validation, state transitions, authorization, identifiers, job lifecycle, evidence/provenance and orchestration invariants. Use models later for bounded inference/judgment, not hidden application glue.

## Progressive Phase Planning

S.A.G.A. adopts a contract-first progressive phase rule for substantial phases.

Before implementation begins:

1. re-establish exact repository/current production reality;
2. write the immediate phase contract with goal, user value, starting state, in/out scope, architecture/data/security impacts, validation matrix, UI review needs, external dependencies, exit criteria and next-phase dependencies;
3. merge that phase contract/governance update to `main` after exact-head validation;
4. only then begin production implementation for the phase on a fresh implementation branch.

Do not fully specify distant phases before predecessor evidence exists.

Before finishing a phase:

1. verify the implementation and exact head;
2. inspect/run required CI;
3. inspect affected rendered UI/responsive states when applicable;
4. update `PROJECT.md`, decisions and the phase contract from verified reality;
5. record blockers and the next concrete phase.

A phase contract does not authorize deployment, cloud spend, or unrelated scope expansion.

## GitHub / Remote-First Convention

GitHub is the source of truth. Prefer repository operations and hosted CI over undocumented scratch/local state.

- use focused branches/PRs;
- batch cohesive connector-driven writes where practical;
- do not merge stale CI evidence after a branch moves;
- do not expose secrets in workflow commands/logs/artifacts;
- live infrastructure mutations must be bounded and intentional;
- provider-cost operations require explicit authorization when they can incur meaningful usage charges;
- ordinary CI should remain free/non-live where practical.

## v2 Validation Baseline

For the web app, use the current scripts in `apps/web/package.json`. Minimum deterministic gate:

```text
cd apps/web
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

Phase-specific access/security/UI tests are added as capabilities arrive. A green legacy Python workflow does not validate v2.

## Documentation Ownership

- current state / active phase / immediate next step -> `PROJECT.md`
- documentation authority/index -> `docs/README.md`
- durable cross-cutting decisions -> `docs/DECISIONS.md`
- current phase scope/evidence -> active `docs/phases/PHASE_V2_*.md`
- frontend architecture -> `docs/v2/FRONTEND_ARCHITECTURE.md`
- UI/UX system -> `docs/v2/UI_SYSTEM.md`
- auth/access/invitation contract -> `docs/v2/ACCESS_AND_INVITATIONS.md`
- broader v2 architecture -> `docs/v2/ARCHITECTURE.md`
- dated evidence -> `docs/validation/` only when useful

Update the existing authoritative file instead of creating competing status documents.

## Scope Discipline

Follow the owner's requested scope. Phase 1 prioritizes the closed-demo main site/frontend/backend/account system before the agentic AI component.

Do not modify RenderLab during S.A.G.A. work. Do not revive the v1 production qualification/R2 repair path unless the owner explicitly reverses the v2 decision.