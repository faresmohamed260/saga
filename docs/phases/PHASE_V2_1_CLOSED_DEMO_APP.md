# S.A.G.A. v2 Phase 1 — Closed-Demo Main Site, Accounts & Invitations

**Status:** COMPLETE

**Tracking:** #151

## Goal

Turn the Phase-0 web foundation into the first real S.A.G.A. v2 application: a closed invite-only demo with account/session boundaries, email invitations, admin access management, and a production-quality narrative workspace shell.

Phase 1 establishes the product/app/auth/UI contracts that later intelligence and generation systems must operate behind.

## Outcome

Phase 1 is complete. The deterministic repository slices and the hosted closed-demo flow are both proven.

An invited user can now:

1. receive a real S.A.G.A. invitation email;
2. confirm it through the supported Supabase invite flow;
3. have the matching S.A.G.A. invitation claimed transactionally;
4. establish a password through the product UI;
5. enter the private Narrative Desk;
6. sign in later from a fresh browser session;
7. lose private access immediately when suspended and regain it after reactivation.

An active admin can:

- create/retry/revoke invitation intent;
- inspect S.A.G.A.-owned account state;
- change bounded role/status state;
- suspend/reactivate accounts;
- operate without treating Auth user metadata as product authorization;
- avoid self-lockout/last-admin failure through database-enforced safeguards.

## Completed Phase Slices

### 1A — contract / governance

- PR #152
- merge `55beaccab011a4c5337db86dd88b52f6d48734c4`

### 1B — account/access foundation

- PR #153
- exact head `e81915942ba9e859c79898ec60fdda38a56235d3`
- merge `5d5b59d17d2bd2f9a5769d2e5c4f9a2b43d1bad9`
- validation: `docs/validation/PHASE_V2_1B_ACCOUNT_ACCESS_2026-09-11.md`

### 1C — auth/access surfaces

- PR #156
- exact head `7bc81877a55af9b47b6bbc96abd7a17e9100fda3`
- merge `319b785e43a169b4ffd7b57cd5be32ad3ef5da67`
- validation: `docs/validation/PHASE_V2_1C_AUTH_ACCESS_2026-09-11.md`

### 1D — Narrative Desk

- concept PR #158
- implementation PR #160
- exact implementation head `8ad0a7eb3bffa3aed394ea86eff562f837239b14`
- merge `f558a282b4743a15d440eada1c6a7ccefe44215c`
- validation: `docs/validation/PHASE_V2_1D_NARRATIVE_DESK_2026-09-11.md`

### 1E — deterministic Admin

- PR #162
- exact head `79929e2c90750c8832025bc57768917edae16f54`
- merge `39dceaf1254ed7616ed1bd9eb640d9d622a73812`
- validation: `docs/validation/PHASE_V2_1E_ADMIN_OPERATIONS_2026-09-11.md`

### 1E — hosted foundation and live proof

- dedicated Supabase project created and active v2 schema applied;
- first-admin bootstrap migrations added and applied;
- dedicated Vercel `saga` project established;
- runtime Supabase configuration wired through secret boundaries;
- custom Resend SMTP configured on verified `mail.saga.faresuniform.uk`;
- public signup disabled;
- production Site URL / redirect allowlist configured;
- real hosted invitation lifecycle proven end-to-end;
- hosted suspension/reactivation proven with a real authenticated session;
- validation: `docs/validation/PHASE_V2_1_HOSTED_AUTH_LIVE_PROOF_2026-09-11.md`.

## Closed-Demo Authorization Contract

S.A.G.A. v2 remains invitation-only.

```text
request/session
  -> SSR Supabase Auth cookie maintenance
  -> fresh server Auth identity verification
  -> S.A.G.A. account-access lookup
  -> role/status decision
  -> bounded product/admin operation
```

Rules:

- anonymous -> sign-in boundary;
- verified Auth identity without S.A.G.A. access -> denied, never auto-admitted;
- suspended account -> private/admin access denied;
- active member -> private application, no Admin;
- active admin -> private application + Admin;
- browser/user metadata never supplies authorization role or actor ID;
- privileged Auth/Admin/Supabase credentials remain server/operator-only.

## Invitation Flow — Proven

```text
active admin
  -> create invitation(email, role)
  -> normalize + persist/reuse pending S.A.G.A. intent
  -> Supabase Auth invite email
  -> Resend SMTP delivery
  -> recipient opens /auth/confirm?token_hash=...&type=invite
  -> Supabase verifies invite token
  -> fresh verified identity/email
  -> transactional S.A.G.A. invitation claim
  -> active S.A.G.A. account
  -> Set Password
  -> private /home
  -> later password sign-in from a fresh session
```

The normal flow was exercised against the public hosted production alias rather than a protected Vercel Preview deployment.

## Hosted Validation Evidence

### Access / suspension proof

GitHub Actions run `34647243289` succeeded against the real hosted stack:

`password sign-in -> /home 200 -> suspend -> /access/suspended -> reactivate -> /home 200`

Supabase recorded a real `last_sign_in_at`. The temporary Auth user and access row were removed after validation.

### Full invitation lifecycle

GitHub Actions run `34647592382` succeeded against the real hosted stack:

`admin API invite -> real Resend/Gmail delivery -> /auth/confirm -> product claim -> Set Password -> /home -> fresh later sign-in`

The proof also checked:

- invitation began `pending`;
- accepted invite settled to `accepted` with matching `accepted_by` and `accepted_at`;
- claimed account became `member` / `active`;
- confirmed Auth identity had `email_confirmed_at`;
- later sign-in updated `last_sign_in_at`;
- all temporary test Auth users, invitation rows, and access rows were cleaned afterward.

## Earlier Preview Failure — Resolved Diagnosis

The first owner invitation attempt failed while Supabase Site URL targeted a Vercel Preview deployment protected by Vercel Authentication.

Isolation showed:

- delivered invite URL structure was correct;
- invite token matched Supabase state;
- direct Supabase `verifyOtp(type: invite)` worked;
- the S.A.G.A. confirmation route worked outside Vercel Preview protection;
- Vercel intercepted the protected Preview before the application could consume the invite.

This was not an application/Auth/template defect. The later public-production proof passed normally.

## UI / Product Contract

Primary principle: **Narrative first, complexity on demand.**

Implemented Phase 1 application surfaces:

- `/sign-in`
- `/auth/confirm`
- `/set-password`
- `/home`
- `/library`
- `/projects`
- `/settings`
- `/admin`

The Narrative Desk and Admin surface have exact-head production-build desktop/narrow rendered evidence, keyboard/focus semantics, touch-size checks, portal-safe theming, and reduced-motion validation.

## Hosted Resources

### Supabase

- project ref: `scmeqnpmhomzcwecjdtu`
- region: `eu-central-1`
- dedicated project; `AI Studio` was not reused
- public signup disabled
- custom Resend SMTP active
- Site URL: `https://saga-pi-two.vercel.app`
- redirect allowlist: public production alias plus future `https://saga.faresuniform.uk/**`

### Vercel

- dedicated project: `saga`
- root: `apps/web`
- temporary public production alias: `https://saga-pi-two.vercel.app`
- historical `studio` project disconnected from S.A.G.A. Git pushes
- Git-triggered Preview/Production deployments disabled by owner policy

### Backblaze B2

Dedicated private bucket is already validated. A scoped runtime key is deferred until an active application flow needs object storage; this is not a Phase 1 closure requirement.

## Validation Matrix

| Claim | State |
|---|---|
| No public signup | validated |
| Private route denial | validated |
| Suspended/unknown denial | validated deterministically and hosted |
| Admin-only reads/mutations | validated |
| Retry-safe invitation intent | validated |
| Settled invitation revoke non-mutating | validated |
| Self/last-admin safeguards | validated |
| Dedicated hosted Supabase | validated |
| Active hosted v2 schema | validated |
| Privileged secret absent from browser | validated structurally |
| Narrative Desk responsive/accessibility | validated |
| Admin responsive/accessibility | validated |
| Real SMTP invitation delivery | validated hosted |
| Invite confirmation + claim + Set Password | validated hosted |
| Fresh later password sign-in | validated hosted |
| Hosted suspension/reactivation | validated hosted |
| Temporary hosted-test cleanup | validated |

## Exit Criteria — Satisfied

Phase 1 required:

1. authoritative Phase-1 contracts — complete;
2. dedicated hosted S.A.G.A. schema — complete;
3. no public self-signup — complete;
4. invite confirmation + credential setup + later sign-in — complete;
5. private routes require fresh verified identity + active account — complete;
6. suspended/unknown identities fail closed — complete;
7. active admins can manage bounded invitation/role/status state — complete;
8. at least one real invitation delivered and accepted — complete;
9. responsive private application shell — complete;
10. no privileged credential/token leakage into browser/repository/logs — complete;
11. exact-head CI/rendered review for shipped repository slices — complete;
12. `PROJECT.md` updated from hosted reality — complete in the Phase 1 closure documentation change.

## Deferred / Non-Blocking

- custom domain cutover to `saga.faresuniform.uk` — issue #165;
- scoped B2 runtime credentials until product object-storage flow becomes active;
- parked PR #172 for optional non-secret deployment-release identity in `/api/health`.

## Next-Phase Direction

Phase 1 being complete removes the previous prohibition on **planning** the next intelligence phase. It does not authorize an unreviewed agent/LLM implementation by itself.

The next session should define an authoritative Phase 2 contract first: select the first meaningful S.A.G.A. intelligence/application capability, map any reused v1 requirements into v2-owned contracts, define data/job/provider boundaries and validation gates, then implement through the normal branch/PR/exact-head workflow.

Any Vercel deployment remains manual-only and requires fresh explicit owner approval for that specific deployment.
