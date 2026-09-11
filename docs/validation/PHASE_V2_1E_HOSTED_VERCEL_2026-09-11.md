# S.A.G.A. v2 Phase 1E — Hosted Vercel Foundation Validation

Date: 2026-09-11

## Scope

Record the first dedicated S.A.G.A. v2 Vercel production deployment after the owner created a new project from `faresmohamed260/saga` with the active web application rooted at `apps/web`.

This evidence proves the deployment foundation only. It does not prove Supabase runtime credentials, hosted Auth configuration, email delivery, or invitation acceptance.

## Dedicated Vercel project

Verified through the connected Vercel account:

- project name: `saga`
- project id: `prj_AKQ8XTGUwpgOZRB9GHMd2lqIfRrc`
- team id: `team_r09C6RLmb2acHapENECQIn9T`
- linked GitHub repository: `faresmohamed260/saga`
- framework: `nextjs`
- Node.js: `24.x`
- repository root selected during import: `apps/web`
- production deployment id: `dpl_ChXHUrsqNB4mmbGCmqnVnGr3ZFyA`
- production state: `READY`
- current temporary production alias: `https://saga-pi-two.vercel.app`

The historical `studio` Vercel project remains separate and was not repurposed.

## Live smoke evidence

Vercel runtime logs for the new production deployment showed successful requests on 2026-09-11:

- `GET /` -> HTTP 200
- `GET /api/health` -> HTTP 200

The deployment is therefore a real healthy Next.js production deployment of the v2 web application, not the retired `apps/studio` configuration.

## Runtime environment contract

The active repository contract in `apps/web/.env.example` requires the following Supabase variables:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

Current application code requires:

- `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` for ordinary server/session Supabase configuration;
- `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` for privileged server-only operations.

B2 runtime variables are intentionally deferred until product object-storage flow becomes active; they are not required for the current hosted Auth/invitation Phase 1 gate.

No privileged secret value is recorded in this document or committed to the repository.

## Production domain direction

The owner specified the eventual canonical production hostname:

- `saga.faresuniform.uk`

This cutover is intentionally not immediate. It is tracked durably in GitHub issue #165: `Launch S.A.G.A. on saga.faresuniform.uk`.

Until that cutover is scheduled, the Vercel production alias may be used for hosted Auth/runtime validation. When the custom domain is attached, Supabase Auth Site URL/redirect configuration and invite/recovery links must be updated to the final production origin.

## Remaining Phase 1 hosted gate

Still unproven:

- Vercel runtime Supabase environment variables wired to the dedicated S.A.G.A. project;
- service-role secret stored only in the deployment secret boundary;
- Supabase Auth Site URL and redirect allowlist;
- invite/recovery templates;
- production-capable SMTP or equivalent Auth email hook;
- first trusted S.A.G.A. admin bootstrap;
- real invitation inbox delivery and acceptance;
- later sign-in;
- hosted suspension/revocation behavior;
- final `saga.faresuniform.uk` domain cutover.

Phase 1 must remain open until those claims are actually proven.
