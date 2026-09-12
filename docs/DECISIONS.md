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

S.A.G.A. invitation records track product intent/state but do not persist reusable raw invite tokens/secrets.

**Consequence:** Application tables cannot become a parallel credential/token store. Invitation acceptance must fail closed if verified Auth identity/email does not match an eligible S.A.G.A. invitation.

### D-022 — Hosted Email Delivery Is an Explicit Operational Gate

**Status:** Accepted

Email invitations/recovery are part of the product requirement, but hosted email configuration cannot be considered solved by application code alone.

**Consequence:** CI may validate code/contract without sending real email. Documentation must distinguish implemented invitation mechanics from verified email deliverability.

### D-023 — S.A.G.A. UI Uses Maintained Mechanics but Owns Its Visual System

**Status:** Accepted

Conventional interactive primitives should come from maintained accessible sources when suitable; S.A.G.A. owns tokens, hierarchy, composition and product-specific behavior.

The primary UX principle is **Narrative first, complexity on demand**.

**Consequence:** Establish S.A.G.A.-specific tokens/primitives and feature components; avoid generic admin-dashboard composition. Motion is purposeful and every animated interaction has a reduced-motion equivalent.

### D-024 — Server Components and Server-Owned Truth Are the Default

**Status:** Accepted

Next.js Server Components own route composition/server data by default. Client Components are limited to browser interaction that actually needs local state.

**Consequence:** Browser code never receives service-role/Auth Admin/object-storage master credentials. Privileged decisions are made in server-owned services/routes after fresh identity verification.

### D-025 — Vercel Deployments Are Manual and Owner-Authorized

**Status:** Accepted — owner decision 2026-09-11

S.A.G.A. does not automatically deploy Git pushes, branches, pull requests, or merges to Vercel.

A Vercel Preview or Production deployment requires explicit owner approval for that specific deployment after the proposed environment, exact Git ref/SHA, and reason for deployment are stated.

**Consequence:** Implementation/merge authorization does not imply deployment authorization. See `docs/operations/VERCEL_DEPLOYMENT_POLICY.md`.

### D-026 — Textual Book Analysis Is Local-First and Subscription-Free

**Status:** Accepted — owner decision 2026-09-12

The required S.A.G.A. book-analysis path must be able to run without paid AI APIs, per-token inference services, hosted GPU subscriptions, or recurring model subscriptions.

The default target is a S.A.G.A.-controlled local analysis host using deterministic code, classical NLP, permissively licensed open-source models, and selective local inference. CPU execution is preferred when adequate; a consumer GPU may accelerate tasks that materially benefit from it.

**Consequence:** Paid hosted AI may be compared experimentally in the future, but it is not a required dependency unless the owner explicitly reverses this decision. Provider convenience is not sufficient justification for adding recurring analysis cost.

### D-027 — Modal Is Reserved for Image/Media Generation, Not Textual Analysis

**Status:** Accepted — owner decision 2026-09-12

Modal remains part of S.A.G.A.'s media/image-generation toolbox but is removed from the active textual book-analysis architecture.

The 2026-09-12 xCoRe/worker Modal hosted-proof work is experimental evidence only. It must not be merged or documented as the permanent textual-analysis runtime.

**Consequence:** Character/entity/coreference, dialogue, event, relationship, timeline, state, causality and higher narrative analysis must not require Modal. Future Modal use for textual analysis requires a new explicit owner decision.

### D-028 — Narrative Analysis Uses a Cost-Aware Evidence Cascade

**Status:** Accepted — owner decision 2026-09-12

For each analysis capability S.A.G.A. should use the cheapest method that safely removes uncertainty before escalating:

1. deterministic structure/rules;
2. lightweight local NLP;
3. specialized local models for unresolved cases;
4. small local generative reasoning only for bounded evidence packets that still require judgment.

Provider/model output is evidence. Deterministic S.A.G.A. code owns canonical IDs, admission/merge policy, source provenance, persistence, state transitions and validation.

**Consequence:** Do not repeatedly prompt a full novel through a large language model merely because a model has a long context window. Build reusable evidence layers, narrow candidate sets, and escalate only the residue that requires semantic judgment.

### D-029 — Analysis Providers Are Adopted by Product Quality and Resource Measurements

**Status:** Accepted — owner decision 2026-09-12

A model/provider is not adopted because it is fashionable, scores well on one benchmark, or was used by v1. S.A.G.A. benchmarks candidates through the same product-owned interfaces and records both quality and whole-book resource cost.

Minimum comparison evidence includes task quality, contamination/false-positive behavior, wall-clock time, peak RAM, peak VRAM when applicable, model/download size, license, determinism/reproducibility and operational complexity.

**Consequence:** Prefer the smaller/faster candidate when downstream product quality is close enough. Non-commercial research weights such as LitBank xCoRe/Maverick checkpoints remain comparative research by default, not unnoticed production dependencies.

### D-030 — Local Analysis Workers Use the Existing Durable Cloud Control Plane

**Status:** Accepted — owner decision 2026-09-12

The preferred textual-analysis topology is an outbound-only local worker that claims durable jobs from the existing Supabase control plane, reads source objects through the existing B2 boundary, invokes local NLP/model sidecars over loopback/private networking, and commits structured evidence/results back through S.A.G.A.-owned contracts.

**Consequence:** The home/local analysis host does not need a public inbound port. Worker downtime does not lose jobs because Postgres remains queue/run truth. The existing TypeScript `services/analysis-worker` stays the preferred orchestration owner unless measurements justify changing it.

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

- final S.A.G.A. brand palette/type pairing after visual concept review;
- exact local NLP/provider winners after Phase-3 quality/resource benchmarks;
- whether local NLP integration uses subprocesses or a loopback HTTP sidecar after measurement of operational simplicity;
- exact local structured-reasoning model/quantization after Phase-3 benchmark evidence;
- whether embeddings materially improve candidate retrieval enough to justify a vector index;
- GPU/provider strategy for future visual/audio generation;
- whether each future B2 object workflow uses direct presigned browser transfer, server-mediated transfer or a hybrid.
