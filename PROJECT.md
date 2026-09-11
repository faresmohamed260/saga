# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a v2 decision explicitly adopts it.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

**Phase 2 — Story Intake & Character Identity Foundation: ACTIVE.**

Authoritative Phase-2 contract:

- `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md`

Phase 2 is the first deliberate reconnection of S.A.G.A. intelligence behind the Phase-1 web/auth/data boundary. Its required end-to-end product loop is:

```text
admitted member
  -> project
  -> supported story source
  -> durable analysis job
  -> separate analysis worker
  -> conservative character identity resolution
  -> character / alias / mention evidence in the private app
```

Do not substitute a general agent framework, chat/RAG layer, canon extractor, or old v1 monolithic runtime for this contract.

Phase 1 authoritative completion evidence remains:

- phase contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`
- hosted Auth live proof: `docs/validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`
- hosted Supabase foundation: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- hosted Vercel foundation: `docs/validation/PHASE_V2_1E_HOSTED_VERCEL_2026-09-11.md`
- deterministic Admin proof: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- deployment policy: `docs/operations/VERCEL_DEPLOYMENT_POLICY.md`

Phase 1 tracking issue: **#151** (closed).

## Phase 2 Direction

The first restored storytelling intelligence capability is **evidence-backed character identity** because stable identity is upstream of canon extraction, character/world modeling, retrieval, narrative generation, and grounded media generation.

Phase 2 intentionally couples identity to the missing v2 product/runtime foundations instead of running it as a free-floating NLP experiment:

- member-owned projects;
- immutable story sources;
- provider-neutral B2 object storage;
- durable Postgres job/control-plane records;
- separate analysis-worker execution outside normal Next.js requests;
- immutable analysis-run provenance;
- conservative character identities, aliases, mentions, and unresolved/quarantined evidence;
- deterministic rerun fingerprints and adversarial identity fixtures;
- private `/projects`, `/library`, and character evidence surfaces.

Initial ingestion scope is UTF-8 `.txt` and `.epub`. PDF/DOCX/OCR, canon extraction, RAG/chat, generative agents, collaboration, and multimedia generation are explicitly out of Phase 2.

The identity policy is precision-first: attachment/coreference evidence may connect a mention to an existing character, but weak evidence — especially pronouns, capitalization artifacts, malformed spans, or non-person entities — may not mint a new canonical character.

## What Phase 1 Proved

Repository and hosted evidence proves:

- invitation-only product; public signup disabled;
- Supabase Auth owns identity/session mechanics;
- S.A.G.A. product records own admission, role, status, and invitation lifecycle;
- fresh server-side identity verification before private/admin access;
- active-admin-only invitation/account operations;
- deterministic retry/revoke semantics and last-admin/self-lockout safeguards;
- real Resend SMTP delivery from the verified `mail.saga.faresuniform.uk` sender domain;
- real hosted invitation confirmation through `/auth/confirm`;
- transactional S.A.G.A. invitation claim;
- real Set Password flow;
- private `/home` access after invitation acceptance;
- later password sign-in from a fresh browser session;
- hosted account suspension immediately denies the same session and routes to `/access/suspended`;
- reactivation restores private access;
- temporary hosted test identities and product records were removed after proof;
- no reusable privileged credential is committed to repository/browser code.

Hosted proof runs:

- access/suspension smoke: GitHub Actions run `34647243289` — success;
- full invitation lifecycle: GitHub Actions run `34647592382` — success.

The earlier failed owner invitation attempt was isolated to Vercel Preview deployment protection, not S.A.G.A. Auth logic, the invite token, Resend, or Supabase. The final proof used the public production alias and passed end-to-end.

## Hosted Resources

### Supabase

Dedicated S.A.G.A. project:

- project ref/id: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- organization id: `imbicfntoeaqubhdcnpe`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`

The old `AI Studio` project was not reused.

Active hosted migration lineage includes:

1. `closed_demo_account_access`
2. `admin_operations`
3. `admin_operation_hardening`
4. `first_admin_bootstrap`
5. `first_admin_invitation_bootstrap`

Supabase Auth currently uses the public production origin `https://saga-pi-two.vercel.app`; the redirect allowlist contains that production origin plus the future `https://saga.faresuniform.uk/**` origin. Public signup remains disabled. Custom SMTP uses Resend through the verified `mail.saga.faresuniform.uk` domain.

### Vercel

Dedicated project:

- project: `saga`
- project id: `prj_AKQ8XTGUwpgOZRB9GHMd2lqIfRrc`
- root: `apps/web`
- framework: Next.js
- stable temporary production alias: `https://saga-pi-two.vercel.app`

The historical `studio` project has been disconnected from the S.A.G.A. Git repository.

**Deployment policy:** automatic Git-triggered Preview and Production deployments are disabled. A request to implement, review, merge, test, or continue work is not deployment permission. Before any Vercel deployment, explain why it is needed, whether it is Preview or Production, and the exact commit/SHA; then obtain explicit owner approval for that specific deployment.

### Backblaze B2

Dedicated private bucket:

- bucket: `saga-v2-faresmohamed260-1207062480`
- region: `us-east-005`
- endpoint: `https://s3.us-east-005.backblazeb2.com`

Bootstrap/master credentials remain operator-only. Phase 2 is the first active product flow that will need object upload/download, but a bucket-scoped runtime application key must be created only when implementation reaches real hosted B2 I/O. That is an explicit credential/infrastructure gate, not a reason to block schema/UI/CI work before it.

## Product / Architecture Boundary

```text
Public browser
  -> landing / sign-in / invite-confirm

Verified admitted user
  -> Next.js application on Vercel
       -> fresh Supabase Auth identity verification
       -> S.A.G.A. account/access resolution
       -> dedicated S.A.G.A. Supabase Postgres/Auth
       -> provider-neutral object storage boundary -> Backblaze B2
       -> durable analysis job/control plane
            -> separate analysis worker
                 -> normalized source
                 -> evidence providers
                 -> deterministic S.A.G.A. identity policy
                 -> immutable analysis run + character evidence
```

Full-book parsing/NLP does not run inside a normal Next.js request. Supabase Postgres is the Phase-2 durable control plane; worker hosting/provider remains deliberately open until the runtime contract is proven and a real host/cost decision is required.

RenderLab remains a separate product and read-only reference for process/UI/architecture conventions. Do not modify it or copy its product code, schema, branding, data, secrets, deployments, or storage assumptions into S.A.G.A.

## Current Web Product

The active application lives under `apps/web/` and includes:

- closed-demo sign-in, invitation confirmation, password setup/change, sign-out;
- private application boundary;
- Narrative Desk shell;
- Home, Library, Projects, Settings;
- active-admin Admin workspace;
- deterministic account/invitation role/status operations;
- responsive desktop/narrow behavior and rendered accessibility checks.

Phase 2 activates the existing Library and Projects placeholders with S.A.G.A.-owned data rather than creating a parallel product shell.

Primary UI principle remains: **Narrative first, complexity on demand.**

## Open / Deferred Items

- custom production domain cutover to `saga.faresuniform.uk` — tracked by issue #165; do not resume without explicit infrastructure/deployment work;
- bucket-scoped B2 runtime credentials — required only when Phase-2 hosted source object I/O begins;
- worker host/provider — intentionally deferred until the Phase-2 runtime boundary and deterministic worker are proven;
- PR #172 (`Expose hosted release identity in health checks`) was closed without merge after Phase 1 proved hosted behavior without it. Reintroduce release fingerprinting only as a fresh current-main change if a later hosted validation gate needs it.

## Next Work

Execute `docs/phases/PHASE_V2_2_STORY_INTAKE_CHARACTER_IDENTITY.md` in order.

Default sequence:

1. Phase 2A — project/source/job/run/identity schema, RLS, database contracts, basic Projects/Library surfaces;
2. Phase 2B — bounded B2 source flow plus deterministic `.txt`/`.epub` ingestion;
3. Phase 2C — provider-neutral evidence contract and precision-first character identity engine;
4. Phase 2D — benchmark baseline, hardening, rendered validation, and hosted end-to-end proof after the required explicit infrastructure/deployment approvals.

Continue normal branch/PR/exact-head CI autonomously until a genuine owner decision, external credential/cost gate, or explicit deployment authorization is required.

Do not deploy to Vercel merely because implementation is merged or ready.

## Validation Convention

For `apps/web`:

```text
npm install --no-audit --no-fund
npm run lint
npm run typecheck
npm run test:unit
npm run build
```

The web CI also applies active `apps/web/supabase/migrations/*.sql` to disposable PostgreSQL and runs database contracts. Rendered UI validation is handled separately through the production-build Chromium workflow.

Phase 2 additionally requires deterministic ingestion/identity fixtures, worker/job contract tests, and a separate literary benchmark harness as defined by the phase contract.

## Working Convention

Every new session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. the active/current phase contract
6. relevant `docs/v2/` architecture/product documents

GitHub is authoritative. Durable decisions, evidence, and phase state go back into the repository; chat history is secondary context only.
