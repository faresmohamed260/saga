# S.A.G.A. v2 Phase 1 Hosted Auth Live-Proof Checkpoint — 2026-09-11

## Scope

This checkpoint records the first hosted owner-invitation attempt and the reason it must be repeated on a public current-code production deployment before Phase 1 can close.

## Hosted foundation proven

- Dedicated Supabase project: `scmeqnpmhomzcwecjdtu` (`eu-central-1`).
- Public signup is disabled.
- Custom SMTP is configured through the verified Resend sending domain `mail.saga.faresuniform.uk`.
- The invitation template routes to S.A.G.A. `/auth/confirm` with a Supabase invite token hash.
- The trusted first-owner bootstrap created exactly one active S.A.G.A. admin and one matching pending product invitation.
- The first-owner email was accepted by Supabase Auth and Resend reported the message as delivered to the recipient mail server.

## First live attempt

The first owner followed the delivered invitation while Supabase Site URL temporarily targeted a current-code Vercel preview deployment.

Observed hosted state after the attempt:

- Auth user exists.
- S.A.G.A. account is `admin` / `active`.
- Product invitation remains `pending`.
- `email_confirmed_at` remains unset.
- `last_sign_in_at` remains unset.
- No password has been established for the Auth user.

Therefore the subsequent sign-in-page reload was not a successful authentication.

## Isolation evidence

The failure is not attributed to the invite token, email template, Supabase project, or S.A.G.A. confirmation implementation:

1. The rendered Resend invitation URL was verified to use the intended host, `/auth/confirm`, `type=invite`, and a non-empty token hash.
2. A non-secret fingerprint comparison proved the token in the delivered message exactly matched the invite token still stored by Supabase Auth.
3. A disposable direct `@supabase/supabase-js` `verifyOtp({ type: "invite", token_hash })` probe succeeded against the same hosted project and publishable key.
4. A disposable probe through the actual S.A.G.A. `/auth/confirm` route running locally confirmed the Auth user successfully. Its later `invalid_invitation` redirect was expected because the disposable probe intentionally had no S.A.G.A. product invitation.
5. An unauthenticated request to the hosted Vercel preview was intercepted by Vercel deployment protection and redirected through `/sso-api` before S.A.G.A. could consume the token.

The protected preview is therefore not an acceptable origin for the real closed-demo invitation acceptance proof.

## Required continuation

- Deploy current `main` publicly to the dedicated `saga` Vercel production project.
- Verify the production deployment source SHA is current and that `/`, `/api/health`, `/sign-in`, and `/auth/confirm` are public without Vercel preview authentication.
- Restore Supabase Site URL to the public production origin while preserving the future `https://saga.faresuniform.uk/**` redirect allowance.
- Reissue the first-owner invitation through a supported Supabase Auth operator path so the new message targets public production.
- Complete invitation confirmation, password setup, authenticated private-app access, later sign-in, and product-invitation settlement.
- Record hosted suspension/revocation behavior before closing Phase 1.

No agent/LLM runtime work is authorized by this checkpoint.
