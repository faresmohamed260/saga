# S.A.G.A. v2 Phase 1 Hosted Auth Live Proof — 2026-09-11

## Result

**PASS — hosted Phase 1 Auth/email/invitation/access behavior is proven end-to-end.**

This document supersedes the earlier checkpoint conclusion that the hosted live proof was still pending. The first attempt failed because a Vercel Preview deployment was protected by Vercel Authentication; the final proof was rerun against the public production alias and passed.

## Hosted Foundation

Dedicated Supabase project:

- project ref/id: `scmeqnpmhomzcwecjdtu`
- region: `eu-central-1`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`

Auth/email configuration proven during the hosted work:

- public signup disabled;
- Site URL restored to `https://saga-pi-two.vercel.app`;
- redirect allowlist reduced to the public production alias plus future `https://saga.faresuniform.uk/**`;
- custom SMTP configured through Resend;
- verified sending domain: `mail.saga.faresuniform.uk`;
- sender: `S.A.G.A. <noreply@mail.saga.faresuniform.uk>`;
- invite subject: `You're invited to S.A.G.A.`;
- invite template routes to `/auth/confirm?token_hash={{ .TokenHash }}&type=invite`.

Dedicated Vercel project:

- project: `saga`
- root: `apps/web`
- public temporary production alias: `https://saga-pi-two.vercel.app`

Automatic Git-triggered Preview and Production deployments are disabled by owner policy. No deployment is implied by merge/implementation/testing requests.

## First Owner Bootstrap

The one-time hosted bootstrap path was added through reviewed migrations and applied to the hosted project:

- `first_admin_bootstrap`
- `first_admin_invitation_bootstrap`

The trusted owner identity was established as an active S.A.G.A. admin. The original invitation attempt was not treated as successful until hosted state was independently checked.

The owner account was later confirmed on the backend with established credentials, active admin access, and settled product invitation state. The normal invitation path was then separately proven with disposable identities so Phase 1 did not rely on the exceptional first-owner bootstrap path as its only evidence.

## Initial Failure and Isolation

The initial owner invitation was delivered successfully, but clicking it while Supabase targeted a Vercel Preview deployment did not consume the invite.

Observed after the failed attempt:

- Auth identity existed;
- product account was `admin` / `active`;
- product invitation remained `pending`;
- invite token remained unconsumed;
- no successful sign-in was recorded.

The following isolation evidence ruled out S.A.G.A./Supabase/Resend defects:

1. the rendered invitation URL had the expected host/path/query shape;
2. a non-secret fingerprint comparison proved the delivered token matched the token Supabase expected;
3. direct `@supabase/supabase-js` `verifyOtp({ type: "invite", token_hash })` succeeded against the hosted project;
4. the actual S.A.G.A. `/auth/confirm` route also verified a disposable invite correctly outside the hosted Preview layer;
5. the protected Vercel Preview intercepted unauthenticated traffic through its own protection flow before S.A.G.A. could consume the invitation.

Conclusion: **Vercel Preview protection caused the failed live attempt.** The application confirmation implementation and invitation template were not the cause.

## Hosted Access / Suspension Proof

GitHub Actions run:

- `34647243289` — success

The proof created a disposable confirmed Auth user and matching active S.A.G.A. member account, generated a real Supabase SSR session, and exercised the public production app.

Verified sequence:

```text
password sign-in
  -> session cookies established
  -> GET /home = 200
  -> account status changed to suspended
  -> same session GET /home redirects to /access/suspended
  -> account reactivated
  -> same session GET /home = 200
  -> Supabase last_sign_in_at present
```

This demonstrates that product authorization is resolved from current S.A.G.A. account state and that an already-authenticated session does not bypass suspension.

Cleanup verification after the run:

- disposable Auth users: `0`
- disposable S.A.G.A. access rows: `0`

## Full Hosted Invitation Lifecycle Proof

GitHub Actions run:

- `34647592382` — success

This proof used the actual public hosted application, actual Supabase Auth, actual S.A.G.A. Admin API, actual Resend delivery, and a real browser session.

Verified sequence:

```text
ephemeral active admin signs in through S.A.G.A.
  -> POST /api/admin/invitations
  -> pending S.A.G.A. invitation intent
  -> Supabase Auth invite accepted for delivery
  -> Resend reports real message delivered to Gmail infrastructure
  -> rendered message contains production /auth/confirm link
  -> browser opens confirmation link
  -> Supabase invite verification succeeds
  -> S.A.G.A. product invitation claim succeeds
  -> browser reaches /set-password
  -> password saved through actual Set Password form
  -> browser reaches /home
  -> invitation row is accepted
  -> member account is active
  -> first browser context closed
  -> brand-new browser context opens /sign-in
  -> later email/password sign-in succeeds
  -> browser reaches /home
```

Postconditions checked during the proof:

- invitation started as `pending`;
- delivery result was `sent`;
- rendered confirmation origin was `https://saga-pi-two.vercel.app`;
- confirmation path was `/auth/confirm`;
- `type=invite` and a non-empty token hash were present;
- invitation became `accepted`;
- `accepted_by` matched the verified invitee Auth user;
- `accepted_at` was populated;
- claimed product account was `member` / `active`;
- `email_confirmed_at` was populated;
- later fresh password sign-in populated/retained `last_sign_in_at`;
- later sign-in reached the private application.

The run emitted the final success marker:

> Hosted invitation lifecycle proof passed: admin API invite -> real Resend delivery -> /auth/confirm -> product claim -> Set password -> /home -> fresh later sign-in.

## Cleanup

All disposable identities/state used by the hosted proofs were deleted after validation.

Independent hosted SQL verification returned:

- invitation-E2E admin Auth users: `0`
- invitation-E2E invitee Auth users: `0`
- access-smoke Auth users: `0`
- invitation-E2E invitation rows: `0`
- invitation-E2E access rows: `0`

Temporary privileged GitHub workflows used for hosted setup/proof were removed after their runs. No plaintext reusable password or privileged provider credential was committed to the repository.

## Deployment Policy Established During Phase 1

The historical `studio` Vercel project was disconnected from S.A.G.A. Git pushes.

The real `saga` project remains linked to the repository, but `apps/web/vercel.json` disables Git-triggered deployments. Repository governance records the rule that every Vercel Preview or Production deployment requires fresh explicit owner permission after the assistant states the reason, deployment type, and exact commit/SHA.

## Phase 1 Conclusion

The hosted evidence now proves the Phase 1 claims that repository-only tests could not establish:

- production Auth configuration;
- authenticated sender/domain and SMTP delivery;
- real invitation delivery;
- invite confirmation;
- product invitation settlement;
- password establishment;
- later password sign-in;
- private-route access;
- hosted suspension/reactivation behavior;
- cleanup/isolation of disposable proof data.

**Phase 1 hosted Auth/email/live-proof gate is complete.**

The earlier hosted Supabase/Vercel foundation validation documents remain useful historical snapshots of setup state, but their then-current statements that Auth/email proof was pending are superseded by this record.
