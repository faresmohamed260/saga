# S.A.G.A. Project

S.A.G.A. is being rebuilt as a web-first storytelling intelligence platform. The product goals remain: ingest books/stories, reconstruct evidence-backed canon, model characters/worlds/timelines, support narrative generation, and eventually produce grounded visual/audio/story outputs. The active architecture is the S.A.G.A. v2 rebuild; pre-v2 runtime material is historical/reference only unless a v2 decision explicitly adopts it.

This file is the short source-of-truth handoff for current work.

## Current Status

**Phase 1 — Closed-Demo Main Site, Accounts & Invitations: COMPLETE.**

Phase 1 established and hosted the application/auth/admin/UI foundation required before agentic intelligence work begins.

Authoritative completion evidence:

- phase contract: `docs/phases/PHASE_V2_1_CLOSED_DEMO_APP.md`
- hosted Auth live proof: `docs/validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`
- hosted Supabase foundation: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`
- hosted Vercel foundation: `docs/validation/PHASE_V2_1E_HOSTED_VERCEL_2026-09-11.md`
- deterministic Admin proof: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- deployment policy: `docs/operations/VERCEL_DEPLOYMENT_POLICY.md`

Phase 1 tracking issue: **#151**.

## What Is Proven

Repository and hosted evidence now proves:

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

Bootstrap/master credentials remain operator-only. Create a bucket-scoped runtime key only when the next product flow actually needs object upload/download; this was intentionally not a Phase 1 blocker.

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
       -> future application/job/agent contracts
```

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

Primary UI principle remains: **Narrative first, complexity on demand.**

## Open / Deferred Items

These are not Phase 1 blockers:

- custom production domain cutover to `saga.faresuniform.uk` — tracked by issue #165;
- bucket-scoped B2 runtime credentials — create only when an active product flow needs them;
- PR #172 (`Expose hosted release identity in health checks`) remains open/parked. Hosted Phase 1 proof completed without it. Re-evaluate it against current `main` before deciding whether to refresh or close it; do not merge/deploy it automatically.

## Next Work

There is no authoritative Phase 2 contract yet. The next session must **define and review the next v2 phase before implementing a new agent/LLM runtime**.

Recommended sequence:

1. verify current remote `main` and read mandatory governance docs;
2. confirm Phase 1 completion documentation is merged and issue #151 reflects closure;
3. inspect open PRs/issues, especially parked PR #172 and custom-domain issue #165;
4. review v1 requirements/algorithms only as historical input, not as active architecture;
5. propose the next v2 phase contract around the first real S.A.G.A. intelligence/application capability behind the now-proven product boundaries;
6. get that phase scope into repository documentation before implementation;
7. continue normal branch/PR/exact-head CI workflow;
8. do not deploy to Vercel without fresh explicit owner authorization.

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

## Working Convention

Every new session starts from:

1. `AGENTS.md`
2. `PROJECT.md`
3. `docs/README.md`
4. `docs/DECISIONS.md`
5. the active/current phase contract
6. relevant `docs/v2/` architecture/product documents

GitHub is authoritative. Durable decisions, evidence, and phase state go back into the repository; chat history is secondary context only.
