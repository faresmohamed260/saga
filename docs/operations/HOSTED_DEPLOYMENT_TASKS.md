# S.A.G.A. Hosted Deployment Tasks

This file tracks hosted tasks that are real project state but may not be completed in the same session as repository implementation.

## Current hosted foundation

- dedicated Supabase project `S.A.G.A.` exists in Frankfurt (`eu-central-1`)
- active v2 migrations are applied to that hosted project
- dedicated Vercel project `saga` exists for `apps/web`
- framework: Next.js
- Node.js: 24.x
- current temporary production alias: `https://saga-pi-two.vercel.app`
- production deployment and `/api/health` are healthy

## Remaining Phase 1 hosted tasks

- wire Vercel runtime to the dedicated S.A.G.A. Supabase project using:
  - `SUPABASE_URL`
  - `SUPABASE_PUBLISHABLE_KEY`
  - `SUPABASE_SERVICE_ROLE_KEY` (server secret only)
- configure Supabase Auth Site URL and redirect allowlist
- verify invite/recovery email templates
- configure production-capable SMTP or equivalent Auth email delivery
- bootstrap the first trusted S.A.G.A. admin through an explicit operator path
- prove a real invitation is delivered, accepted, claimed, and followed by credential setup and later sign-in
- prove hosted suspension/revocation behavior

## Deferred production domain

The owner selected `saga.faresuniform.uk` as the eventual canonical production hostname.

This is deliberately **not an immediate blocker** for the current hosted Auth/runtime validation. Track final cutover in GitHub issue #165.

When cutover is scheduled:

- attach `saga.faresuniform.uk` to the dedicated Vercel `saga` project
- configure DNS and verify TLS
- change Supabase Auth Site URL/redirect allowlist to the custom domain
- verify invite/recovery links use the final origin
- re-run public/auth/private/health smoke validation

Do not silently repurpose the historical Vercel `studio` project or the separate RenderLab deployment.
