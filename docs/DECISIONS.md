# S.A.G.A. Durable Decisions

This file records cross-cutting decisions future sessions must not silently reinterpret. Git history preserves the full decision evolution; this file owns the currently applicable decision set.

## Active v3 Decisions

### D-001 — Repository Is the Persistent Source of Truth

**Status:** Accepted

Current repository code and authoritative documentation define S.A.G.A. state. Chat/project memory is supplementary continuity.

**Consequence:** Durable architecture, phase state, validation evidence and blockers must be recorded in GitHub.

### D-033 — Narrative Compiler Is the Accepted Target Analysis Architecture

**Status:** Accepted — owner decision 2026-10-06

S.A.G.A. v3 replaces the v2 provider/evidence cascade as the accepted long-term textual-analysis architecture.

The v3 engine is a local typed compiler:

```text
source compiler
  -> semantic lexer
  -> global linkers
  -> Narrative IR
  -> specialist reasoners
  -> global constraint solvers
  -> canonical Narrative IR
  -> derived projections
```

Models produce evidence; S.A.G.A. owns identity, global consistency, acceptance state, provenance and canon.

The existing v2 runtime is not deleted or rewritten in place. It remains the operational and measured comparison baseline until v3 capabilities pass shadow qualification and are explicitly promoted.

**Consequence:** New semantic implementation work must target the v3 Narrative IR/stage contracts rather than extending BookNLP/provider-specific structures as the permanent architecture. External model outputs are adapters into S.A.G.A.-owned contracts, not architectural truth.

### D-034 — Narrative IR/Postgres Own Canonical Semantic State; Graphs Are Projections

**Status:** Accepted — owner decision 2026-10-06

S.A.G.A. v3 defines a typed Narrative IR that distinguishes source spans, mentions, entities, event mentions/events, observations/facts, state deltas, temporal constraints and other semantic objects.

When v3 production persistence is introduced, canonical semantic state belongs in PostgreSQL/Supabase under S.A.G.A.-owned schemas and provenance rules. Neo4j, vector indexes, visualization graphs and generation-oriented structures are derived/rebuildable projections.

**Consequence:** No graph database or model-provider identity is allowed to become an independent source of canon. A derived projection must be rebuildable from canonical source/IR state.

### D-035 — V3 Semantic Inference Is Python-Native; Existing Durable Control Plane Remains

**Status:** Accepted — owner decision 2026-10-06

The v3 semantic compiler is implemented as an isolated Python-native package/runtime because the target NLP/encoder/model ecosystem is Python-native and because semantic model scheduling should be owned in one long-lived compiler process.

Supabase remains durable queue/run truth. The existing application/auth/B2/control-plane boundaries remain in place. The current TypeScript analysis worker may supervise/invoke the compiler during migration, but semantic stage logic, Narrative IR and model orchestration belong in the Python compiler rather than being split into provider-shaped TypeScript adapters.

**Consequence:** V3.0 does not authorize replacement of Supabase jobs, B2, web/auth infrastructure, or production read paths. The compiler begins in shadow/benchmark mode.

### D-036 — V3 Uses Typed Static Dataflow, Not Agentic Control, for Book Compilation

**Status:** Accepted — owner decision 2026-10-06

The core book-analysis runtime is a typed dependency DAG with content-addressed artifacts, deterministic invalidation/caching, explicit stage versions and bounded learned components. An LLM/agent does not decide which mandatory compiler pass runs next.

Agentic orchestration remains appropriate for later interactive workflows, generation, research, or user-directed tool use, but not as the source of truth for deterministic compilation order.

**Consequence:** Compiler-stage dependencies and invalidation rules must be explicit and testable. LangGraph or another agent framework must not become foundational to the required analysis path merely for orchestration convenience.

### D-037 — V3 Adoption Optimizes Supported Coverage at High Precision

**Status:** Accepted — owner decision 2026-10-06

For semantic/canonical decisions, S.A.G.A. prefers unresolved output over unsafe assertions. The principal v3 product target is supported coverage at **>=97% precision** where suitable gold exists, together with task-specific false-merge/fragmentation/contamination metrics and resource measurements.

**Consequence:** A system does not win by maximizing recall while contaminating canon. Qualification must report unresolved rate and useful coverage alongside precision, recall, runtime, RAM/VRAM, model revision, license and provenance completeness.

## Earlier v2 Decisions That Remain Applicable Unless Explicitly Superseded

### D-011 — S.A.G.A. v2 Was a Fresh Rebuild

**Status:** Historical but still informative

The pre-v2 Python/nine-stage runtime is historical/reference material rather than an implementation compatibility requirement. V3 likewise reuses requirements, evaluations and proven invariants selectively rather than bulk-porting old package boundaries.

### D-012 — Product Surface Is Web-First

**Status:** Accepted

The main user-facing product remains Next.js/React/TypeScript on the web with Supabase application state/auth and dedicated object storage. The v3 semantic-engine reboot does not reverse this product decision.

### D-013 — AI Runtime Operates Behind Application-Owned Contracts

**Status:** Accepted

AI/analysis systems operate behind the application data, auth, job and storage boundaries rather than becoming the top-level product architecture.

### D-014 — Backblaze B2 Is the Object Store

**Status:** Accepted

Supabase owns relational application state; B2 owns source files, generated media, exports and other large objects for the hobby/demo deployment.

### D-015 — Object Storage Is Provider-Neutral at the Domain Boundary

**Status:** Accepted

Feature/domain code depends on a S.A.G.A.-owned storage interface rather than directly on B2-specific clients.

### D-016 — B2 Master Key Is Bootstrap-Only

**Status:** Accepted

Master credentials are not normal web runtime credentials and must never be printed or committed. Normal runtime access uses scoped credentials and explicit storage boundaries.

### D-017 — RenderLab Is Read-Only Reference Material

**Status:** Accepted

RenderLab is a separate product. S.A.G.A. may borrow proven engineering principles only after translating them into S.A.G.A.-owned contracts. It must not share product code, product state, credentials, deployments or identity.

### D-018 — Substantial Phases Are Contract-First

**Status:** Accepted

For substantial phases, an execution-ready contract/governance update is merged to `main` before production implementation begins.

**Consequence:** Planning is not implementation evidence. A merged contract does not by itself authorize deployment, paid services or promotion of experimental models.

### D-019 — Product Is a Closed Invite-Only Demo

**Status:** Accepted

There is no ordinary public self-service signup. Product access begins through invited accounts.

### D-020 — Supabase Auth Owns Identity; S.A.G.A. Owns Product Access

**Status:** Accepted

Authorization uses verified Supabase identity plus S.A.G.A.-owned role/status, not browser-supplied IDs, unsigned metadata or invitation text.

### D-021 — Invitation Secrets Are Auth-Provider Concerns

**Status:** Accepted

Application tables track invitation intent/state but do not become a reusable token/credential store.

### D-022 — Hosted Email Delivery Is an Explicit Operational Gate

**Status:** Accepted

Invitation/recovery code does not imply verified email deliverability. Operational configuration must be validated separately.

### D-023 — S.A.G.A. Owns Its Visual System

**Status:** Accepted

Maintained accessible primitives may provide mechanics, but S.A.G.A. owns tokens, composition, hierarchy and product-specific behavior. The UX principle remains **Narrative first, complexity on demand**.

### D-024 — Server Components and Server-Owned Truth Are the Default

**Status:** Accepted

Privileged decisions remain server-owned. Browser code never receives service-role/Auth Admin/object-storage master credentials.

### D-025 — Vercel Deployments Are Manual and Owner-Authorized

**Status:** Accepted

Implementation or merge authorization does not imply deployment authorization. Each Preview/Production deployment requires explicit owner approval for the stated environment/ref/reason.

### D-026 — Textual Book Analysis Is Local-First and Subscription-Free

**Status:** Accepted — strengthened by v3

The required analysis path must run without paid AI APIs, per-token inference services, hosted GPU subscriptions or recurring model subscriptions. Local deterministic code, open-source/open-weight models and consumer CPU/GPU compute are the default.

### D-027 — Modal Is Reserved for Image/Media Generation

**Status:** Accepted

Modal is not a required textual-analysis dependency. Textual character/entity/coreference/dialogue/event/state/timeline/causality processing remains local-first.

### D-028 — Spend Compute Only Where Semantic Ambiguity Requires It

**Status:** Accepted, architectural form superseded by D-033/D-036

The v2 phrasing was a cost-aware evidence cascade. V3 retains the underlying principle—deterministic/cheap broad passes and selective expensive reasoning—but implements it as typed compiler stages rather than a provider cascade.

### D-029 — Models Are Adopted by Product Quality and Resource Measurements

**Status:** Accepted

A model is not adopted because it is fashionable or wins an external leaderboard. S.A.G.A. records task quality, contamination/false positives, wall time, RAM, VRAM, artifact size, license, determinism and operational complexity through product-owned benchmarks.

Non-commercial research checkpoints may be comparative references but cannot silently enter the production dependency set.

### D-030 — Local Analysis Uses the Existing Durable Cloud Control Plane

**Status:** Accepted, refined by D-035

The analysis host remains outbound-oriented: Supabase owns durable job/run truth and B2 remains the source-object boundary. D-035 moves semantic compiler/model logic into the Python-native v3 engine while preserving this control plane.

### D-031 — Modal Accounts Are Partitioned by Project

**Status:** Accepted

S.A.G.A. owns `modal-03` through `modal-41`; RenderLab owns `modal-01`, `modal-02`, and `modal-42` through `modal-47`. Credential presence is not authorization. This remains relevant to media/image workflows and does not weaken D-027.

### D-032 — BookNLP Repeated Analysis Uses Persistent Local Stdio

**Status:** Accepted for the frozen v2/BookNLP baseline only

Measured v2 work showed persistent loaded BookNLP stdio preserves validated semantic output while reducing repeated-request latency relative to one-shot process startup.

**Consequence:** Preserve this behavior when reproducing the v2 baseline. It does not make BookNLP a v3 architectural dependency and does not imply other v3 models should use the same transport without measurement.

## V3.0 Model/Implementation Decisions Still Open

Resolve these through [`phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md`](phases/PHASE_V3_0_NARRATIVE_COMPILER_FOUNDATION.md) and measured evidence rather than assumption:

- exact GLiNER2-class package/checkpoint/revision adopted for lexer qualification;
- exact Ettin-class checkpoint/scoring formulation for identity qualification;
- whether learned embeddings materially improve identity candidate generation beyond lexical/context features;
- threshold/calibration policy needed to meet the >=97% supported-precision target;
- exact physical Postgres indexes/cardinality choices after V3.0 measurements;
- whether the TypeScript worker invokes the compiler by bounded stdio/process protocol or another private local transport after runtime measurement;
- which semantic stage should follow identity/entity V3.0 based on measured failure modes.

## Historical v1 Decisions

D-002 through D-010 described the pre-v2 runtime and remain historical evidence only. The clean v1 boundary immediately before the v2 rebuild was:

`b689e17bf2b70ea6c2ade0c3795bb85bb048d57b`

Do not reactivate the v1 runtime as the active architecture unless the owner explicitly makes a new decision.