# S.A.G.A. Durable Decisions

This file records cross-cutting decisions future sessions must not silently reinterpret.

## Active v2 Decisions

### D-001 — Repository Is the Persistent Source of Truth

**Status:** Accepted

Current repository code and authoritative documentation define S.A.G.A. state. Chat/project memory is supplementary continuity.

**Consequence:** Durable architecture, phase state, validation evidence and blockers must be recorded in GitHub.

### D-011 — S.A.G.A. v2 Is a Fresh Rebuild

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. keeps its product goals/intended capabilities but abandons the previous implementation architecture as the active system.

The pre-v2 Python/nine-stage system is historical/reference material. v2 is not required to preserve its runtime package boundaries, deployment topology, persistence abstractions, qualification control plane, provider routing or orchestration design.

**Consequence:** Reuse requirements, algorithms, evaluations, schemas, prompts and lessons selectively; do not bulk-port v1 code or treat v1 compatibility as a default requirement.

### D-012 — v2 Is Web-First

**Status:** Accepted

The main application is built first as a web product using:

- Next.js + React + TypeScript;
- Vercel deployment target;
- Supabase Postgres/Auth/Realtime;
- Cloudflare DNS/CDN/security where useful;
- dedicated object storage behind a S.A.G.A.-owned interface.

The active product surface is `apps/web/`.

**Consequence:** User-facing domain workflows, application state, auth, jobs and storage contracts are designed before the new agentic AI runtime.

### D-013 — Agentic AI Follows the Web/Application Foundation

**Status:** Accepted

The new agentic AI subsystem is intentionally deferred until the web frontend/backend, application data model, storage, authentication, job lifecycle and deployment contracts are stable enough to consume.

**Consequence:** Phase 0/1 must not recreate the old pipeline as top-level product architecture. Future agents operate behind application-owned contracts and write structured application state/artifacts.

### D-014 — Backblaze B2 Is the v2 Object Store

**Status:** Accepted

S.A.G.A. v2 will not use the existing shared Cloudflare R2 allocation. Backblaze B2 is selected for dedicated S.A.G.A. object storage for the hobby/demo deployment.

Supabase owns structured relational application state. B2 owns source files, generated media, exports and other large binary/object payloads.

**Consequence:** Do not make new S.A.G.A. storage depend on RenderLab/Fares Uniform R2 resources. Keep the object-store boundary replaceable.

### D-015 — Object Storage Is Provider-Neutral at the Domain Boundary

**Status:** Accepted

Feature/domain code depends on a S.A.G.A.-owned storage interface rather than directly on B2/AWS SDK clients. The B2 runtime implementation may use Backblaze's S3-compatible API once a scoped application key exists.

**Consequence:** Vendor details remain in the server storage infrastructure boundary. Switching to another S3-compatible store should not require rewriting domain features.

### D-016 — B2 Master Key Is Bootstrap-Only

**Status:** Accepted

Repository secrets `SAGA_B2_KEY_ID` and `SAGA_B2_MASTER_APPLICATION_KEY` are available for bounded Backblaze account/bootstrap operations. Their values must never be printed or committed.

Backblaze master application keys are not S3-compatible, so they are not the normal web runtime credential.

**Consequence:** GitHub Actions may use the master key for bounded bucket administration/smoke tests. Normal web storage later uses a bucket-scoped application key and explicit S3 endpoint configuration.

### D-017 — RenderLab Is a Read-Only Engineering/UI Reference, Not a Shared Product

**Status:** Accepted — strengthened by owner instruction 2026-09-11

`faresmohamed260/renderlab` is a separate product. S.A.G.A. may inspect its current repository documentation for proven setup/process/architecture/UI governance conventions.

Permitted reference categories include repository-first continuity, progressive phase contracts, frontend/server/infrastructure ownership, maintained primitives, responsive/accessibility/reduced-motion rules, closed-beta invitation/access concepts and remote CI/render validation.

**Consequence:** S.A.G.A. work must not modify RenderLab. Do not copy RenderLab product code, visual identity, page composition, routes, database/schema names, product data, Supabase/R2 credentials, storage resources or deployments. An adopted principle becomes authoritative only after it is translated into a S.A.G.A.-owned contract/implementation.

### D-018 — Progressive v2 Phases Are Contract-First

**Status:** Accepted

Fully specify only the immediate v2 phase and keep later phases at roadmap level until predecessor evidence is stable.

For substantial phases, the execution-ready contract/governance update is merged to `main` before production implementation begins.

Current order:

1. Phase 0 — web foundation + storage bootstrap — **complete** through PR #149 / `261b75ff2a60dfcada681af6b6c918c1ff5e3366`;
2. Phase 1 — closed-demo main site frontend/backend + account/invitation system — **active**;
3. later — application jobs/agentic AI foundation and progressive restoration of S.A.G.A. intelligence/generation capabilities.

**Consequence:** Planning detail is not implementation evidence; a merged contract does not authorize deployment or paid/live provider execution.

### D-019 — S.A.G.A. v2 Is a Closed Invite-Only Demo

**Status:** Accepted — owner decision 2026-09-11

The v2 application is not a public self-service SaaS. There is no ordinary public create-account flow.

A public landing/brand surface may exist, but application access requires an invited account.

**Consequence:** Access begins from an admin-created email invitation. Sign-in, invite confirmation, password setup/recovery and account management are designed for a bounded demo population rather than open registration.

### D-020 — Supabase Auth Owns Identity; S.A.G.A. Owns Product Access

**Status:** Accepted

Supabase Auth is the identity/session authority. S.A.G.A. owns product admission/authorization in S.A.G.A.-specific relational records.

The initial account model uses a verified Auth user ID plus S.A.G.A.-owned role/status. Invitations begin from normalized email and become account access only after verified invitation/session identity is established.

**Consequence:** Never authorize from browser-supplied IDs, `user_metadata`, unsigned role claims or invitation query text. Private application authorization uses fresh server verification of the current Auth identity plus active S.A.G.A. access state. Admin operations require fresh active-admin authorization.

### D-021 — Invitation Secrets Are Auth-Provider Concerns, Not Application Records

**Status:** Accepted

S.A.G.A. invitation records track product intent/state (normalized email, intended role, inviter, lifecycle metadata) but do not persist reusable raw invite tokens/secrets.

Invite verification is performed through Supabase Auth's supported server-side confirmation flow; S.A.G.A. then claims the matching pending invitation under server control.

**Consequence:** Application tables cannot become a parallel credential/token store. Invitation acceptance must fail closed if verified Auth identity/email does not match an eligible S.A.G.A. invitation.

### D-022 — Hosted Email Delivery Is an Explicit Operational Gate

**Status:** Accepted

Email invitations/recovery are part of the product requirement, but hosted email configuration cannot be considered solved by application code alone.

Production/demo readiness requires verified Supabase Site URL/redirect allowlist, invite/recovery templates using supported confirmation links/token hashes, and production-capable custom SMTP or an equivalent Auth email hook with appropriate sender-domain authentication and rate limits.

**Consequence:** CI may validate code/contract without sending real email. Documentation must distinguish implemented invitation mechanics from verified email deliverability.

### D-023 — S.A.G.A. UI Uses Maintained Mechanics but Owns Its Visual System

**Status:** Accepted

Conventional interactive primitives should come from maintained accessible sources when suitable; S.A.G.A. owns tokens, hierarchy, composition and product-specific behavior.

The primary UX principle is **Narrative first, complexity on demand**. Core surfaces are story/canon/entity/evidence/media workspaces, not generic admin dashboards and not mirrors of internal AI/provider stages.

**Consequence:** Establish S.A.G.A.-specific tokens/primitives and feature components; avoid repeated raw hand-styled controls, arbitrary one-off values, card-within-card nesting and generic card-grid dashboards. Motion is purposeful, responsive/accessibility behavior is designed from the start and every animated interaction has a reduced-motion equivalent.

### D-024 — Server Components and Server-Owned Truth Are the Default

**Status:** Accepted

Next.js Server Components own route composition/server data by default. Client Components are limited to browser interaction that actually needs local state.

Account authorization, durable library/project truth, invitations/admin state and future job truth remain server-owned. No global client account/admin/data store is introduced merely for convenience.

**Consequence:** Browser code never receives service-role/Auth Admin/object-storage master credentials. Privileged decisions are made in server-owned services/routes after fresh identity verification.

### D-025 — Vercel Deployments Are Manual and Owner-Authorized

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. does not automatically deploy Git pushes, branches, pull requests, or merges to Vercel. The active web project keeps Git-triggered deployments disabled through `apps/web/vercel.json`.

A Vercel Preview or Production deployment requires explicit owner approval for that specific deployment after the proposed environment, exact Git ref/SHA, and reason for deployment are stated. Repository implementation/merge authorization does not imply deployment authorization.

The historical Vercel `studio` project was disconnected from `faresmohamed260/saga` on 2026-09-11 and must remain disconnected unless the owner explicitly reverses that decision.

**Consequence:** Normal validation uses GitHub Actions and repository-owned deterministic checks. Agents may propose a manual Vercel deployment for major cohesive updates, hosted-integration testing, or owner review, but must wait for explicit approval before triggering it. Approval is one-time and does not authorize later deployments. See `docs/operations/VERCEL_DEPLOYMENT_POLICY.md`.

## Still-Applicable General Principles From v1

These principles remain useful across the rebuild even though their old implementation context is historical:

- research is evidence, not implementation state;
- analysis-derived canon should become durable application state before generation relies on it;
- qualification/evaluation claims must be tied to reproducible source/configuration;
- cross-project cleanup/reuse requires explicit ownership evidence;
- deterministic code should own schemas, validation, identifiers, state transitions, authorization and orchestration invariants.

## Historical v1 Decisions

Earlier D-002 through D-010 described the pre-v2 contract-driven Python architecture, nine-stage runtime, Studio retirement and v1 qualification/recovery boundaries. They remain **historical evidence about v1**, not active v2 constraints except where an active decision above deliberately preserves a principle.

The clean v1 boundary immediately before the rebuild is:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

Do not reactivate the v1 Phase-0 qualification/R2 repair path unless the owner explicitly reverses the v2 rebuild decision.

## Open v2 Decisions

Resolve these only in the phase that needs them:

- exact new S.A.G.A. Supabase project after explicit organization/cost confirmation;
- exact custom SMTP/Auth email-hook provider and sender domain;
- final S.A.G.A. brand palette/type pairing after visual concept review;
- final runtime hosting/queue architecture for long-running agent jobs beyond Vercel request limits;
- agent framework/model-provider architecture;
- GPU/provider strategy for future visual/audio generation;
- whether each future B2 object workflow uses direct presigned browser transfer, server-mediated transfer or a hybrid.
