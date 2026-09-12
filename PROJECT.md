# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a v2 decision explicitly adopts it.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

- **Phase 2A — Product/Data Foundation: COMPLETE (repository/CI slice).**
- **Phase 2B — Source Storage & Deterministic Ingestion: COMPLETE (repository/CI slice).**
- **Phase 2C — Character Identity Engine: NEXT.**
- **Phase 2D — Qualification / Hosted Proof: PENDING.**

Authoritative Phase-2 contract:

- `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Authoritative deterministic validation:

- `docs/validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `docs/validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`

Phase 2 tracking issue: **#176**.

The required Phase-2 loop remains:

```text
admitted member
  -> project
  -> .txt/.epub source
  -> durable analysis job
  -> separate analysis worker
  -> deterministic normalized source
  -> precision-first character identity resolution
  -> character / alias / mention evidence in the private app
```

Do not substitute a general agent framework, chat/RAG layer, canon extractor, or the historical v1 runtime for this contract.

## Phase 2 Direction

Character identity is the first restored storytelling-intelligence capability because stable identity is upstream of canon extraction, character/world modeling, retrieval, narrative generation, and grounded media generation.

The product invariant is precision-first identity admission:

> Attachment/coreference evidence may connect a mention to an existing character, but weak evidence may not mint a new canonical character.

Pronouns, sentence-initial capitalization, malformed spans, ambiguous discourse tokens, and non-person evidence are not canonical seeds. Unresolved/quarantined evidence is valid output and must not be silently promoted.

## Phase 2A Completed Baseline

Phase 2A implementation PR **#177**:

- exact implementation head: `51147ddf5855a43c3b50770502f2cf9f8fdf1f54`
- merge: `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`
- closure merge: `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`

It established:

- member-owned projects/source metadata with forced RLS;
- durable analysis jobs with idempotent enqueue and atomic lease-based claiming;
- immutable analysis-run provenance;
- character/alias/mention result foundations;
- real `/projects`, `/projects/[projectId]`, and `/library` data surfaces;
- disposable-Postgres owner/isolation/lease/retry contracts.

## Phase 2B Completed Baseline

Phase 2B implementation PR **#179**:

- exact implementation head: `20a0e222aac42208b45a4faac3814208afd50762`
- merge: `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`

It establishes the deterministic repository/CI ingestion boundary:

- owner-scoped source upload intents;
- server-generated B2 object keys using owner/project/source/content IDs rather than filenames;
- short-lived direct-to-B2 signed PUT uploads behind `ObjectStorage`;
- browser SHA-256 declaration plus signed object metadata;
- independent server-side B2 HEAD verification before enqueue;
- no ingestion enqueue when observed upload metadata mismatches;
- private signed original-source read path;
- immutable normalized-source and normalized-section persistence with forced owner RLS;
- kind-scoped durable worker leases;
- a new v2-owned `services/analysis-worker/` runtime, separate from historical Python/runtime surfaces;
- worker-side re-hashing of the actual downloaded source bytes;
- deterministic strict-UTF-8 TXT normalization;
- deterministic EPUB package/spine normalization with archive/path safety limits;
- Unicode code-point offsets, stable structural locators and deterministic semantic fingerprints;
- bounded transient retry versus terminal normalization failure behavior;
- project-workspace source upload UI and current Library/Home ingestion state;
- golden TXT/EPUB fixtures and a dedicated Analysis Worker CI workflow.

Exact-head qualification on `20a0e222aac42208b45a4faac3814208afd50762`:

- Web CI `34661457524` — success
- Analysis Worker CI `34661457497` — success
- Visual Review `34661457496` — success
- Backend Architecture CI `34661457500` — success
- Required Check Compatibility `34661457516` — success

Rendered artifact: `10287611789`, digest `ccadb4a2bd382ea7d69e34b9d72aa8f1ac0b6bbe5d5c8b2f0de8ad43daa61fb6`.

No hosted database/storage/worker/Vercel mutation is implied by this repository completion.

## Hosted Resources / Reality

### Supabase

Dedicated S.A.G.A. project:

- ref/id: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- public signup disabled
- custom Resend SMTP active

The existing `AI Studio` project was not reused.

Phase-2A/2B migrations are merged and disposable-Postgres qualified. This handoff does **not** claim those Phase-2 migrations have been applied to hosted Supabase. Hosted migration state must be proven explicitly when Phase 2D qualification begins.

### Vercel

Dedicated project:

- project: `saga`
- root: `apps/web`
- stable temporary production alias: `https://saga-pi-two.vercel.app`

Automatic Git-triggered Preview and Production deployments are disabled.

**Deployment rule:** implementation, review, merge, testing, or a generic instruction to continue is not Vercel deployment permission. Before any deployment, state why it is needed, Preview vs Production, and the exact commit/SHA; then obtain fresh explicit owner approval for that deployment.

No Vercel deployment was performed for Phase 2A or 2B.

### Backblaze B2

Dedicated private bucket:

- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- endpoint: `https://s3.us-east-005.backblazeb2.com`

Bootstrap/master credentials remain operator-only.

The Phase-2B repository upload/read flow is implemented, but real hosted object I/O is not yet enabled. A bucket-scoped non-master runtime application key and any required browser-upload CORS configuration are explicit external gates for Phase 2D hosted proof. They do **not** block Phase 2C repository/CI work.

### Worker hosting

`services/analysis-worker/` is now an active v2 runtime boundary. Its code/contract is CI-proven, but no permanent worker host/provider has been selected or deployed. Host/account/cost selection remains deliberately deferred until hosted qualification requires it.

## Product / Architecture Boundary

```text
Browser
  -> Next.js web application
       -> fresh Supabase Auth/account-access checks
       -> owner-scoped project/source/result reads
       -> provider-neutral ObjectStorage -> Backblaze B2
       -> durable Postgres job/control plane
            -> services/analysis-worker
                 -> deterministic normalization
                 -> Phase 2C evidence provider boundary
                 -> deterministic identity policy
                 -> immutable run + character evidence
```

Full-book parsing/NLP does not execute inside a normal Next.js request.

RenderLab remains a separate product and read-only reference for process/UI/architecture conventions only. Do not copy its product code, schema, branding, data, secrets, deployments, or storage assumptions into S.A.G.A.

## Current Web Product

The active application under `apps/web/` includes:

- closed-demo sign-in/invitation/password flows;
- private Narrative Desk shell;
- Home, Library, Projects, Settings and active-admin Admin;
- project create/list/open;
- project Overview, Sources, Analysis and Characters sections;
- bounded `.txt`/`.epub` source upload with browser hashing, direct signed object upload, server verification and durable ingestion queue state;
- Library source records/status;
- private signed original-source read path;
- responsive/accessibility rendered validation.

The Characters section still lacks the Phase-2C evidence-backed identity result UI. That is the next active product slice.

Primary UI principle: **Narrative first, complexity on demand.**

## Next Work — Phase 2C

Continue `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` with **Phase 2C — Character Identity Engine**.

Immediate repository goals:

1. define a provider-neutral normalized mention/span/coreference evidence contract in `services/analysis-worker`;
2. add deterministic recorded/synthetic provider fixtures so policy CI needs no heavyweight model download;
3. implement precision-first mention admission and deterministic canonical seeding/name clustering;
4. implement attachment/quarantine/unresolved rules, including late strong-name stabilization without raw-text rewriting;
5. ensure pronouns, malformed spans, discourse/function tokens and non-person typed spans cannot mint canonicals;
6. produce deterministic semantic identity fingerprints excluding UUID/timestamp noise;
7. add a transactional worker persistence boundary for Character/Alias/Mention results tied to an immutable `character_identity` analysis run;
8. enqueue/claim `character_identity` work durably without coupling it to the ingestion worker claim path;
9. add adversarial fixtures for historical failure classes;
10. expose canonical characters, aliases, representative mentions, evidence/admission tier, unresolved evidence and run provenance in the private project UI;
11. keep provider selection benchmarkable and do not introduce a generative LLM dependency.

Continue branch/PR/exact-head CI autonomously. Do not stop for the deferred B2 runtime key or worker-host choice while Phase 2C can still be implemented deterministically in repository/CI.

Stop only at a genuine owner decision, external credential/cost gate, or explicit deployment authorization gate.

## Open / Deferred Items

- custom production domain `saga.faresuniform.uk` — issue #165; not part of current Phase-2 work unless explicitly resumed;
- bucket-scoped B2 runtime credential + upload CORS — Phase-2D hosted-proof gate;
- worker host/provider/cost — Phase-2D hosted-proof gate;
- application of Phase-2 migrations to hosted Supabase — Phase-2D hosted-proof step;
- Vercel deployment — separately approval-gated;
- PR #172 release identity concept — closed without merge; reintroduce only if a future hosted proof specifically needs it.

## Validation Convention

For `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

For `services/analysis-worker` use its dedicated TypeScript typecheck and deterministic fixture suite through `.github/workflows/v2-analysis-worker-ci.yml`.

Web CI applies active v2 Supabase migrations to disposable PostgreSQL and runs database contracts. Rendered product validation is handled by `.github/workflows/v2-visual-review.yml`.

## Working Convention

Every new session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. the active/current phase contract
6. relevant `docs/v2/` architecture/product documents

GitHub is authoritative. Durable decisions, evidence, and phase state go back into the repository; chat history is secondary context only.
