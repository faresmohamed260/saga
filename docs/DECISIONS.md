# S.A.G.A. Durable Decisions

This file records cross-cutting decisions future sessions must not silently reinterpret.

## Active v2 Decisions

### D-001 — Repository Is the Persistent Source of Truth

**Status:** Accepted

Current repository code and authoritative documentation define S.A.G.A. state. Chat/project memory is supplementary continuity.

**Consequence:** Durable architecture, phase state, validation evidence, and blockers must be recorded in GitHub.

### D-011 — S.A.G.A. v2 Is a Fresh Rebuild

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. keeps its product goals and intended capabilities but abandons the previous implementation architecture as the active system.

The pre-v2 Python/nine-stage system becomes historical/reference material. v2 is not required to preserve its runtime package boundaries, deployment topology, persistence abstractions, qualification control plane, provider routing, or orchestration design.

**Consequence:** Reuse requirements, algorithms, evaluations, schemas, prompts, and lessons selectively; do not bulk-port v1 code or treat v1 compatibility as a default requirement.

### D-012 — v2 Is Web-First

**Status:** Accepted

The main application is built first as a web product. Initial technology family:

- Next.js + React + TypeScript;
- Vercel deployment;
- Supabase Postgres/Auth/Realtime;
- Cloudflare DNS/CDN/security where useful;
- dedicated object storage behind a S.A.G.A.-owned interface.

The active product surface is `apps/web/`.

**Consequence:** User-facing domain workflows, application state, auth, jobs, and storage contracts are designed before the new agentic AI runtime.

### D-013 — Agentic AI Follows the Web/Application Foundation

**Status:** Accepted

The new agentic AI subsystem is intentionally deferred until the web frontend/backend, application data model, storage, authentication, job lifecycle, and deployment contracts are stable enough to consume.

**Consequence:** Early v2 phases must not recreate the old pipeline as the top-level product architecture. Future agents operate behind application-owned contracts and write structured application state/artifacts.

### D-014 — Backblaze B2 Is the v2 Object Store

**Status:** Accepted

S.A.G.A. v2 will not use the existing shared Cloudflare R2 allocation. Backblaze B2 is selected for S.A.G.A.-dedicated object storage for the hobby/demo deployment.

Supabase owns structured relational application state. B2 owns source files, generated media, exports, and other large binary/object payloads.

**Consequence:** Do not make new S.A.G.A. storage depend on the RenderLab/Fares Uniform R2 allocation. Keep the object-store boundary replaceable.

### D-015 — Object Storage Is Provider-Neutral at the Domain Boundary

**Status:** Accepted

Feature/domain code depends on a S.A.G.A.-owned storage interface rather than directly on B2/AWS SDK clients. The B2 runtime implementation may use Backblaze's S3-compatible API once a scoped application key exists.

**Consequence:** Vendor details remain in `apps/web/src/server/storage/` or a later dedicated infrastructure package. Switching to another S3-compatible store should not require rewriting domain features.

### D-016 — B2 Master Key Is Bootstrap-Only

**Status:** Accepted

Repository secrets `SAGA_B2_KEY_ID` and `SAGA_B2_MASTER_APPLICATION_KEY` are available for bounded Backblaze account/bootstrap operations. Their values must never be printed or committed.

Backblaze master application keys are not S3-compatible, so they are not the normal web runtime credential.

**Consequence:** GitHub Actions may use the master key for bounded B2 account/bootstrap work. Normal web storage uses a bucket-scoped application key and explicit S3 endpoint configuration.

### D-017 — RenderLab Is Read-Only Engineering/UI Reference

**Status:** Accepted — clarified by owner 2026-09-11

`faresmohamed260/renderlab` is a separate project. S.A.G.A. may inspect it read-only for proven setup/architecture/UI-governance patterns.

Useful reference areas include repository-first continuity, Next.js/Supabase server-client boundaries, identity vs product-admission separation, invitation/admin security lessons, maintained primitive sourcing, semantic tokens, responsive/rendered verification, and progressive phase/design workflow.

**Consequence:** Never modify RenderLab for S.A.G.A. work and never treat its product state as S.A.G.A. state. Do not copy/share its routes, schema/table names, brand/visual identity, R2 resources, credentials, deployment state, or implementation wholesale. Express useful principles as S.A.G.A.-owned contracts and reimplement independently.

### D-018 — Progressive v2 Phases

**Status:** Accepted

Fully specify the immediate v2 phase and keep later phases at roadmap level until current implementation evidence is stable.

Current order:

1. Phase 0 — web foundation + storage bootstrap — **completed/merged**;
2. Phase 1 — closed-demo main site frontend/backend + account/invitation foundation — **active**;
3. later — agentic AI foundation and progressive restoration of S.A.G.A. intelligence/generation capabilities.

### D-019 — S.A.G.A. v2 Is a Closed, Invitation-Only Demo

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. v2 is not an open-registration public SaaS product.

- there is no public self-service signup;
- private application access requires a verified identity plus active S.A.G.A. product admission;
- invitations are created by authorized S.A.G.A. admins for email addresses;
- invitations are delivered by email through a server-only Auth/email-provider boundary;
- Supabase Auth identity/session state and S.A.G.A. product admission/role/status are separate concerns;
- unknown, pending, suspended, revoked, or unverifiable identities fail closed.

**Consequence:** A valid Supabase user is not automatically a S.A.G.A. member. Public UI must not advertise account creation. Product roles come from S.A.G.A.-owned server records, not browser/user metadata. Email invitation responses must avoid address/account enumeration. Production email readiness requires verified hosted Auth redirect/template/SMTP configuration.

### D-020 — UI Governance Is S.A.G.A.-Owned, Maintained-Primitive First

**Status:** Accepted

S.A.G.A. owns its UI identity and design rules in `docs/v2/UI_SYSTEM.md` and `docs/v2/DESIGN_WORKFLOW.md`.

The default product rule is **story first, machinery second**. UI should be simple by default and progressively disclose complexity.

Conventional interactive mechanics should use S.A.G.A.-normalized maintained primitives before custom generic implementations. Semantic design tokens should replace arbitrary repeated visual values. Ordinary feature work preserves accepted composition; explicit visual redesign requires design-before-code and separate rendered fidelity review.

**Consequence:** Do not let external component libraries or RenderLab become a competing visual system. Build success alone is not UI approval; affected surfaces require responsive rendered review.

### D-021 — Server-Verified Identity and S.A.G.A. Admission Are Separate Security Gates

**Status:** Accepted

Supabase Auth is the identity/session authority, but private S.A.G.A. access is authorized by S.A.G.A.-owned account state on the server.

**Consequence:** Private routes resolve a fresh server-verified identity and then active S.A.G.A. access. Browser-supplied user IDs, `user_metadata` roles, or stale client state are not authorization. Supabase service-role/Auth-admin capability remains server-only; admin operations reverify active admin access.

## Still-Applicable General Principles From v1

These principles remain useful across the rebuild even though their old implementation context is historical:

- research is evidence, not implementation state;
- analysis-derived canon should become durable application state before generation relies on it;
- qualification/evaluation claims must be tied to reproducible source/configuration;
- cross-project cleanup/reuse requires explicit ownership evidence;
- deterministic code should own schemas, validation, identifiers, state transitions, authorization, and orchestration invariants.

## Historical v1 Decisions

Earlier D-002 through D-010 decisions described the pre-v2 contract-driven Python architecture, nine-stage runtime, Studio retirement, and v1 qualification/recovery boundaries. They remain valid **historical evidence about v1**, but they do not constrain v2 architecture except where an active decision above explicitly preserves a principle.

The clean v1 boundary immediately before the rebuild is:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

Do not reactivate the v1 Phase-0 qualification/R2 repair path unless the owner explicitly reverses the v2 rebuild decision.

## Open v2 Decisions

Resolve these only in the phase that needs them:

- exact S.A.G.A.-owned Supabase project instance and live rollout timing;
- production SMTP/email-hook provider and sender domain for invitation/recovery mail;
- final runtime hosting/queue architecture for long-running agent jobs beyond Vercel request limits;
- agent framework/model-provider architecture;
- GPU/provider strategy for future visual/audio generation;
- whether each B2 object type should use direct presigned browser upload, server-mediated operations, or a hybrid.
