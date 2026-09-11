# S.A.G.A. v2 Phase 1 — Hosted End-to-End Validation

**Date:** 2026-09-11

**Phase:** S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Result:** PASS — hosted Auth, email, invitation, private-access, suspension, reactivation, and revocation behavior required by the Phase 1 contract were proven against the dedicated S.A.G.A. hosted environment.

## Scope

This evidence closes the hosted portion of Phase 1. It supplements the earlier deterministic database, auth/access, Narrative Desk, Admin, and hosted-Supabase validation records.

The proof was executed against the existing public production deployment and dedicated hosted Supabase project. It did **not** trigger a new Vercel deployment.

## Hosted Environment

### Supabase

- project: `S.A.G.A.`
- project ref: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`
- active v2 migrations applied through the invitation-aware first-admin bootstrap lineage

### Web runtime

- Vercel project: `saga`
- stable public production alias used by the proof: `https://saga-pi-two.vercel.app`
- production deployment source commit used by the hosted proof: `b171d96f9a7391be1bef3894a29804ec95a53822`
- `/api/health` returned HTTP 200 before the live proofs
- `/sign-in` returned HTTP 200 without Vercel Preview protection

The repository later merged the manual-only Vercel deployment policy through PR #173 / merge `4c592a5590fdd46ac075a20def4b9d03c169f880`. Git-triggered Preview and Production deployments are disabled; that policy merge intentionally did not replace the already-working production runtime used here.

## Hosted Auth / Email Configuration

Verified hosted configuration:

- Supabase Auth Site URL: `https://saga-pi-two.vercel.app`
- public self-signup: disabled
- redirect allowlist:
  - `https://saga-pi-two.vercel.app/**`
  - `https://saga.faresuniform.uk/**`
- stale protected-preview redirect origin removed
- custom SMTP enabled through Resend
- sender: `S.A.G.A. <noreply@mail.saga.faresuniform.uk>`
- Resend sending domain `mail.saga.faresuniform.uk` verified through Cloudflare DNS
- invitation subject: `You're invited to S.A.G.A.`
- invitation template uses the supported token-hash confirmation route at `/auth/confirm`

The scoped Supabase Management PAT and provider credentials remained in GitHub Actions secret boundaries. Their values were not written to repository files or validation logs.

## First Trusted Admin Bootstrap

The first trusted owner/admin identity exists in hosted Supabase and is represented by an active S.A.G.A. admin access row. The initial browser invitation attempt was disrupted by Vercel Preview protection, so that owner identity was repaired through privileged operator tooling rather than being used as the clean normal-flow proof.

That incident is not counted as the Phase 1 invitation-lifecycle proof. The clean proof below used a new disposable invited member and exercised the ordinary product flow from beginning to end against the public production origin.

## Proof 1 — Hosted Password Session + Suspension / Reactivation

Temporary branch: `ops/hosted-access-smoke`

Successful run:

- GitHub Actions run: `34647243289`
- exact workflow head: `2b230f77e9ff6c0a582bc46f55d456c5a8690eb1`
- job: `103420848632`

The run created a disposable Auth user and active S.A.G.A. member with a runner-generated random password, then proved:

1. hosted `signInWithPassword` succeeds;
2. Supabase SSR cookies are established;
3. active member request to production `/home` returns HTTP 200;
4. changing the S.A.G.A. access row to `suspended` does not destroy the Auth session but causes the same `/home` request to redirect to `/access/suspended`;
5. reactivating the S.A.G.A. access row restores `/home` HTTP 200;
6. Supabase records a real `last_sign_in_at`.

Run output included:

> Hosted access proof passed: password sign-in -> /home 200 -> suspension redirect -> reactivation /home 200.

Independent cleanup verification after the run returned:

- disposable Auth users: `0`
- disposable access rows: `0`

The temporary workflow was deleted from its ops branch after validation and was never merged to `main`.

## Proof 2 — Normal Invitation Delivery, Acceptance, Password Setup, and Later Sign-In

Temporary branch: `ops/hosted-invitation-e2e`

Successful run:

- GitHub Actions run: `34647592382`
- exact workflow head: `ee7fa83320dfcc0e152f1334c84f957cf55f0e7e`
- job: `103421972351`

The run used an ephemeral active S.A.G.A. admin and a disposable Gmail plus-address. It exercised the ordinary product flow rather than calling the claim routine directly:

1. ephemeral admin signs in through the real production `/sign-in` UI;
2. authenticated admin calls the real production `POST /api/admin/invitations` endpoint;
3. S.A.G.A. persists a pending invitation intent;
4. Supabase Auth sends the real invitation through the configured Resend SMTP path;
5. Resend reports the invitation as delivered to the recipient mail infrastructure;
6. the rendered email confirmation URL is retrieved under a secret boundary and validated for the production origin, `/auth/confirm`, `token_hash`, and `type=invite` without logging the reusable token;
7. a fresh browser context opens the exact delivered confirmation link;
8. production `/auth/confirm` verifies the Supabase invite and claims the matching S.A.G.A. invitation;
9. the browser reaches the real `/set-password` surface;
10. a runner-generated password is submitted through the actual Set Password form;
11. the newly admitted member reaches private `/home`;
12. the invitation row is verified `accepted`, with matching `accepted_by` and populated `accepted_at`;
13. the access row is verified `member` + `active`;
14. the invitation browser context is destroyed;
15. a completely new browser context signs in later through the real `/sign-in` page using the established password;
16. later sign-in reaches `/home`, and Supabase records confirmed email plus `last_sign_in_at`.

Run output included:

> Hosted invitation lifecycle proof passed: admin API invite -> real Resend delivery -> /auth/confirm -> product claim -> Set password -> /home -> fresh later sign-in.

Independent cleanup verification after the run returned:

- disposable Auth users: `0`
- disposable invitation rows: `0`
- disposable access rows: `0`

The temporary workflow was deleted from its ops branch after validation and was never merged to `main`.

## Proof 3 — Hosted Pending-Invitation Revocation

Temporary branch: `ops/hosted-revocation-smoke`

Successful run:

- GitHub Actions run: `34647880892`
- exact workflow head: `62f184dcb763059382e9c6907bed6d398542cd3d`
- job: `103422900910`

The run created an ephemeral active admin plus a pending product invitation intent and proved:

1. the admin obtains a real hosted Supabase password session and SSR cookies;
2. the authenticated session calls production `DELETE /api/admin/invitations/[invitationId]`;
3. the API returns HTTP 200 and `status: revoked`;
4. the hosted invitation row persists `status = revoked` with `revoked_at` populated.

Run output included:

> Hosted invitation revocation proof passed: authenticated admin DELETE -> revoked state persisted.

Independent cleanup verification after the run returned:

- disposable Auth users: `0`
- disposable invitation rows: `0`
- disposable access rows: `0`

The temporary workflow was deleted from its ops branch after validation and was never merged to `main`.

## Existing Deterministic / Rendered Evidence Still Applies

Phase 1 hosted evidence builds on the already-merged deterministic and rendered validation:

- Phase 1B account/access foundation: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`
- Phase 1C auth/access surfaces: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`
- Phase 1D Narrative Desk: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`
- Phase 1E deterministic Admin: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`
- Phase 1E hosted Supabase foundation: `docs/validation/PHASE_V2_1E_HOSTED_SUPABASE_2026-09-11.md`

In particular, PR #162 exact-head CI and visual review already proved active-admin operations, role/status safeguards, responsive Admin UI, narrow touch targets, keyboard/focus behavior, and reduced-motion behavior. The new live proofs establish that those server-owned contracts also operate against the real hosted providers and public production origin.

## Phase 1 Exit-Criteria Mapping

| Exit criterion | Evidence |
|---|---|
| Phase 1 contracts authoritative | merged Phase 1 contract/governance and this completion reconciliation |
| dedicated hosted S.A.G.A. schema | hosted project + migration validation |
| no public self-signup | hosted Auth config `disable_signup = true` + no signup product route |
| confirmation + credential setup + later sign-in | run `34647592382` |
| private routes require verified identity + active product account | deterministic 1C evidence + run `34647243289` |
| suspended/unknown identities fail closed | deterministic 1C evidence + live suspension redirect in run `34647243289` |
| admin invitation / role / status operations | deterministic 1E evidence; live invite and revoke proofs |
| real invitation delivered and accepted | Resend-delivered lifecycle in run `34647592382` |
| responsive application shell and narrative IA | Phase 1D / 1E production render evidence |
| no privileged credential/token leak | structural checks + secret-bound live workflows; temporary workflows removed |
| exact-head CI and rendered review | earlier implementation PR exact-head gates plus completion PR exact-head gates |
| current state / next step recorded | `PROJECT.md` and Phase 1 contract updated by the completion PR |

## Deferred Items That Are Not Phase 1 Blockers

- final custom public domain `saga.faresuniform.uk` remains tracked separately; the current stable public production alias is functional;
- a scoped non-master B2 runtime key is created when a product object-upload flow actually activates;
- agentic AI, long-running job/runtime orchestration, canon extraction, generation, and media execution remain outside Phase 1 and require a new immediate phase contract before implementation.

## Conclusion

The previously pending hosted claims are now **validated**. Phase 1 can close once this evidence and the authoritative status reconciliation pass exact-head repository validation and are merged to `main`.
