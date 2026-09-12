# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a v2 decision explicitly adopts it.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

- **Phase 2A — Product/Data Foundation: COMPLETE (repository/CI slice).**
- **Phase 2B — Source Storage & Deterministic Ingestion: COMPLETE (repository/CI slice).**
- **Phase 2C — Character Identity Engine: COMPLETE (repository/CI slice).**
- **Phase 2D — Qualification / Hosted Proof: ACTIVE.**

Authoritative Phase-2 contract:

- `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Authoritative deterministic validation:

- `docs/validation/PHASE_V2_2A_PRODUCT_DATA_FOUNDATION_2026-09-12.md`
- `docs/validation/PHASE_V2_2B_SOURCE_INGESTION_2026-09-12.md`
- `docs/validation/PHASE_V2_2C_CHARACTER_IDENTITY_2026-09-12.md`

Phase 2 tracking issue: **#176**.

The implemented repository/CI loop is now:

```text
admitted member
  -> project
  -> .txt/.epub source
  -> durable source-ingestion job
  -> separate analysis worker
  -> deterministic normalized source
  -> durable character-identity job
  -> provider-neutral evidence
  -> S.A.G.A. precision-first identity policy
  -> immutable run + character / alias / mention evidence
  -> private project evidence UI
```

Do not substitute a general agent framework, chat/RAG layer, canon extractor, or historical v1 runtime for this contract.

## Phase 2C Completed Baseline

Phase 2C implementation PR **#181**:

- exact qualified implementation head: `9643a6c997f37074b8e6827c4ad0027858040f77`
- merge: `191e2e4ab4ad9d4023f198b295922b5675e8d269`

It establishes:

- provider-neutral normalized identity evidence contracts;
- deterministic recorded/synthetic provider evidence for CI;
- optional provider-neutral HTTPS evidence adapter;
- strong clean PERSON-like proper-name canonical admission;
- pronoun/nominal attachment without canonical seeding;
- quarantine of blocked discourse/function words, malformed spans and non-person evidence;
- provider-cluster attachment without allowing contaminated clusters to force incompatible canonicals together;
- full-evidence late-name stabilization/backfill without raw-text rewriting;
- deterministic alias clustering, semantic character keys and output fingerprints;
- atomic successful-ingestion -> `character_identity` job handoff;
- kind-scoped identity worker claims and bounded retry/terminal-failure behavior;
- transactional immutable Character/Alias/Mention persistence with provider/resolver provenance;
- private owner/RLS-scoped character evidence reads and project UI;
- adversarial historical-failure fixtures and exact-head rendered evidence validation.

Exact-head qualification on `9643a6c997f37074b8e6827c4ad0027858040f77`:

- Web CI `34664464705` — success
- Analysis Worker CI `34664464659` — success
- Visual Review `34664464727` — success
- Backend Architecture CI `34664464655` — success
- Required Check Compatibility `34664464685` — success

Rendered artifact: `10288233985` (`saga-v2-phase-2c-visual-review`), digest `03fc83ee8dad10a05e7edc33db77d7295cc02f70e90e0a4fdd3cd5dfb04d7f55`.

No hosted database/storage/worker/provider/Vercel mutation is implied by Phase-2C repository completion.

## Earlier Phase-2 Baselines

### Phase 2A

Implementation PR #177, merge `7a053697e874d8fb6e0b03571b7cf0f2e885dd61`; closure merge `4b405ecacdb10e2a15b702210c2cdfef4daa2a9b`.

Established member-owned projects/sources, forced RLS, durable lease-based analysis jobs, immutable analysis runs, result-table foundations, and real Projects/Library private surfaces.

### Phase 2B

Implementation PR #179, exact head `20a0e222aac42208b45a4faac3814208afd50762`, merge `fad0b8e5a3cc5c0e819d86fb41f50fe587574aab`; closure merge `7cf98cffd5b49a85d1b70cc38a6ed6bf0796b8de`.

Established bounded signed B2 upload/read contracts, upload-completion verification, separate v2 analysis worker, deterministic TXT/EPUB normalization, normalized structure persistence, worker-side byte re-hashing, golden fixtures and source-ingestion UI.

## Hosted Resources / Reality

### Supabase

Dedicated S.A.G.A. project:

- ref/id: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- public signup disabled
- custom Resend SMTP active

The historical `AI Studio` project was not reused.

Phase-2A/2B/2C migrations are repository-merged and disposable-Postgres qualified. This handoff does **not** claim those Phase-2 migrations have been applied to hosted Supabase. Hosted migration state must be proven explicitly in Phase 2D.

### Vercel

Dedicated project:

- project: `saga`
- root: `apps/web`
- stable temporary production alias: `https://saga-pi-two.vercel.app`

Automatic Git-triggered Preview and Production deployments are disabled.

**Deployment rule:** implementation, review, merge, testing, or a generic instruction to continue is not Vercel deployment permission. Before any Vercel deployment, state why it is needed, Preview vs Production, and the exact commit/SHA; then obtain fresh explicit owner approval for that deployment.

No Vercel deployment was performed for Phase 2A, 2B, or 2C.

### Backblaze B2

Dedicated private bucket:

- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- endpoint: `https://s3.us-east-005.backblazeb2.com`

Bootstrap/master credentials remain operator-only. The repository upload/read flow is implemented, but real hosted source I/O still requires a bucket-scoped non-master runtime application key and any required browser-upload CORS configuration.

### Worker / evidence provider

`services/analysis-worker/` is an active v2 runtime boundary and is repository/CI-proven. No permanent worker host is selected or deployed. The production identity evidence provider/model is also deliberately unselected; provider choice must be benchmarkable against the normalized evidence contract and S.A.G.A. identity policy.

## Current Product / Architecture Boundary

```text
Browser
  -> Next.js application
       -> fresh Supabase Auth/account-access checks
       -> owner-scoped project/source/result reads
       -> provider-neutral ObjectStorage -> Backblaze B2
       -> durable Postgres job/control plane
            -> services/analysis-worker
                 -> deterministic normalization
                 -> provider-neutral identity evidence
                 -> deterministic S.A.G.A. identity policy
                 -> immutable analysis run + evidence
```

Full-book parsing/NLP does not execute inside a normal Next.js request.

RenderLab remains a separate product and read-only process/UI/architecture reference. Do not copy its product code, schema, branding, data, secrets, deployments, or storage assumptions into S.A.G.A.

## Current Web Product

The active application under `apps/web/` includes:

- closed-demo sign-in/invitation/password flows;
- private Narrative Desk shell;
- Home, Library, Projects, Settings and active-admin Admin;
- project create/list/open;
- bounded `.txt`/`.epub` source upload with browser hashing, direct signed object upload, server verification and durable ingestion state;
- private signed original-source read path;
- Analysis job state;
- Characters evidence UI with canonical identities, admission tier, aliases, representative mentions, unresolved/quarantined evidence and provider/resolver provenance;
- responsive/accessibility rendered validation.

Primary UI principle: **Narrative first, complexity on demand.**

## Next Work — Phase 2D

Continue `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` with **Phase 2D — Qualification**.

Repository-only work may continue autonomously before hosted gates:

1. harden retry/idempotency/concurrency behavior across ingestion and identity jobs;
2. add a literature-oriented offline benchmark/evaluation harness that consumes normalized evidence/result contracts rather than production databases;
3. record the first v2 identity baseline, including false-canonical creation, fragmentation/merge behavior, mention quality and coreference/identity metrics where gold data permits;
4. keep heavyweight model/dataset downloads out of normal merge CI;
5. package final deterministic/rendered qualification evidence and exact-head run IDs;
6. identify the minimal hosted proof plan without performing hosted mutations prematurely.

Stop when Phase 2D reaches a genuine hosted gate requiring:

- bucket-scoped B2 runtime credentials and/or browser-upload CORS mutation;
- applying Phase-2 migrations to hosted S.A.G.A. Supabase;
- selecting/authorizing a worker host/provider/cost path;
- selecting credentials for a paid/proprietary evidence provider;
- any Vercel deployment.

A Vercel deployment always requires fresh explicit approval with reason, deployment type and exact SHA.

## Open / Deferred Items

- custom production domain `saga.faresuniform.uk` — issue #165; not part of current Phase-2 work unless explicitly resumed;
- bucket-scoped B2 runtime credential + upload CORS — Phase-2D hosted-proof gate;
- hosted application of Phase-2 migrations — Phase-2D hosted-proof step;
- worker host/provider/cost — Phase-2D hosted-proof gate;
- production identity evidence provider selection — benchmark/credential gate;
- Vercel deployment — explicit per-deployment owner approval required;
- PR #172 release identity concept — closed without merge; reconsider only if a future hosted proof specifically needs it.

## Validation Convention

For `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

For `services/analysis-worker`, use its dedicated TypeScript typecheck and deterministic fixture suite through `.github/workflows/v2-analysis-worker-ci.yml`.

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
