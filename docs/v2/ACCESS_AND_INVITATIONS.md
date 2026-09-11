# S.A.G.A. v2 Access, Accounts & Invitations

## Purpose

Define the closed-demo identity/admission model for S.A.G.A. v2.

The design is informed by proven closed-beta/account patterns observed in the read-only RenderLab repository, but this is a S.A.G.A.-owned contract. S.A.G.A. does not reuse RenderLab tables, code, routes, Supabase project, Auth users, credentials, email templates or deployment state.

## Product Rule

S.A.G.A. v2 is an **invite-only closed demo**.

There is no ordinary public self-signup.

A public landing page and sign-in page may exist. Private application content is available only to users who:

1. have a current verified Supabase Auth identity;
2. have matching S.A.G.A.-owned account access;
3. have `status=active`;
4. satisfy any route-specific role requirement.

## Authority Split

### Supabase Auth owns

- credentials;
- password hashing;
- login/session issuance;
- refresh tokens;
- invitation/recovery token verification;
- email-address verification state as exposed by Auth;
- session revocation/current-user truth.

### S.A.G.A. owns

- whether a verified Auth identity is admitted to the product;
- product role (`member|admin` initially);
- product account status (`active|suspended` initially);
- invitation intent/state by normalized email;
- inviter/acceptance/audit metadata;
- future demo-specific quotas/policies if needed.

Do not create parallel password/session/token infrastructure in S.A.G.A. tables.

## Trust Boundary

```text
request/browser cookie
  -> SSR cookie/signature/refresh plumbing
  -> fresh server Auth verification (`getUser()`-equivalent)
  -> verified non-anonymous Auth user ID/email
  -> S.A.G.A. account-access lookup
  -> role/status authorization
  -> owner/admin-scoped product operation
```

Important distinction:

- a proxy/middleware claim/JWT check may maintain SSR cookies or perform a cheap early redirect;
- private product authorization still needs a fresh server check when immediate session revocation matters;
- the browser never chooses the effective user ID/role/status.

## Initial Data Model

The concrete migration may tune names/types while preserving the semantics below.

### `saga_account_access`

One row per admitted Supabase Auth user.

Suggested fields:

```text
user_id         uuid primary key
role            text/check or enum: member | admin
status          text/check or enum: active | suspended
invited_by      uuid nullable
accepted_at     timestamptz not null
created_at      timestamptz not null
updated_at      timestamptz not null
```

Constraints/invariants:

- `user_id` is a verified Auth user ID;
- role/status are server-owned product authorization values;
- no browser grant allows arbitrary role/status mutation;
- timestamps use server/database time;
- role/status mutation is audit-friendly and deterministic;
- later account/profile fields that are not authorization state should not silently become authorization inputs.

### `saga_invitations`

Tracks product invitation intent/lifecycle, not credential secrets.

Suggested fields:

```text
id                uuid primary key
email_normalized  text/citext not null
email_display     text not null
intended_role     member | admin
status            pending | accepted | revoked | expired
invited_by        uuid not null
invited_at        timestamptz not null
expires_at        timestamptz nullable/required after hosted policy is fixed
accepted_by       uuid nullable
accepted_at       timestamptz nullable
revoked_at        timestamptz nullable
created_at        timestamptz not null
updated_at        timestamptz not null
```

Constraints/invariants:

- email normalization is server/database-owned and consistent;
- at most one active pending invitation for the same normalized email unless a deliberate resend/versioning contract says otherwise;
- accepted/revoked/expired invitations cannot be reclaimed;
- raw Supabase invite tokens, OTP values or reusable confirmation secrets are never stored;
- acceptance requires a freshly verified Auth identity whose normalized email matches the eligible invitation;
- the invitation claim and account creation/update happen transactionally.

## Email Normalization

Normalize before uniqueness/lookup.

Initial rule:

- trim surrounding whitespace;
- Unicode/lowercase normalization suitable for email comparison;
- preserve a display/original form separately when useful;
- do not invent provider-specific Gmail-style dot/plus canonicalization.

Database uniqueness and application normalization must agree.

## Invitation Lifecycle

### Create

Only an active S.A.G.A. admin may create an invitation.

Server flow:

```text
admin request
  -> fresh Auth verification
  -> active S.A.G.A. admin check
  -> validate + normalize email
  -> reject/resolve conflicting active account/invitation state
  -> persist pending invitation intent
  -> call supported Supabase Auth admin invite operation
  -> return bounded product outcome
```

The Supabase Auth operation may send the email directly through hosted SMTP/email-hook configuration. If a future implementation chooses generated links + a separate mail provider, the same rule applies: the generated secret/link is server-only and must not be persisted in ordinary application rows/logs.

### Delivery failure

Email/provider failure must not silently claim success.

The service should leave deterministic state that allows an admin to retry or revoke. Exact retry semantics are fixed during implementation once the chosen Supabase invite API behavior is verified.

Never echo raw Auth tokens or provider error payloads to the browser.

### Confirm

The invitation email points to the S.A.G.A. confirmation endpoint using a supported Supabase confirmation/token-hash flow.

Conceptual flow:

```text
GET /auth/confirm?...supported auth values...
  -> validate type/path
  -> server verifies/exchanges Auth token/hash
  -> fresh Auth user obtained
  -> safe same-origin next-path selected
  -> claim eligible S.A.G.A. invitation by verified normalized email
  -> establish active S.A.G.A. account
  -> redirect to password setup or private home
```

The confirmation endpoint must reject:

- missing/invalid/expired/consumed Auth confirmation;
- hostile/external redirect targets;
- anonymous/missing verified identity;
- email mismatch;
- no eligible pending invitation;
- revoked/expired/accepted invitation;
- conflicting account state.

### Claim transaction

Claiming is server-owned and race-safe.

Within one transaction/privileged routine:

1. lock or otherwise serialize the invitation row;
2. verify invitation remains eligible;
3. verify normalized invitation email equals the freshly verified Auth email;
4. create/upsert the S.A.G.A. account with intended role and `active` status according to the accepted policy;
5. mark invitation accepted with `accepted_by`/`accepted_at`;
6. return the resulting product-access state.

Two concurrent claims must not create inconsistent access or accept one invitation twice.

## Sign-In

Public `/sign-in` uses Supabase Auth's supported credential flow.

Rules:

- no Create Account link/action;
- generic user-facing error treatment where useful to avoid unnecessary account enumeration;
- after successful Auth sign-in, private route resolution still checks S.A.G.A. access;
- a valid Supabase account without S.A.G.A. access is not automatically admitted;
- suspended S.A.G.A. users remain denied from private product routes even if Auth credentials are valid.

## Password Setup / Recovery

Invitation acceptance may establish a session and direct the user to `/set-password`.

Rules:

- password mutation uses supported Supabase Auth user/session APIs;
- set-password access must be bound to a freshly established valid session/confirmation context;
- hostile `next` redirects are rejected;
- recovery email flow may later reuse the same server confirmation boundary with a different allowed Auth type;
- security/account routes may remain available to suspended signed-in users if needed to change password/sign out, while private product data remains denied.

Do not put a reusable recovery/invite secret into ordinary query state after verification.

## Private Account Resolver

Create one server-owned resolver with a narrow product result, e.g. conceptually:

```ts
type SagaAccount = {
  userId: string;
  email: string;
  role: "member" | "admin";
  status: "active" | "suspended";
};
```

It should:

1. perform fresh Auth verification;
2. reject Auth errors/anonymous/missing user;
3. load only S.A.G.A.-owned access state;
4. reject missing/suspended access for private product use;
5. return a product-level account object, not the raw privileged Supabase client/user directory.

Settings/security flows may use a separate identity resolver when they intentionally need verified identity even if product access is suspended. Keep that distinction explicit.

## Admin Authorization

Admin page/API authorization uses:

```text
fresh Auth identity
  + saga_account_access.role = admin
  + saga_account_access.status = active
```

Never trust:

- `user_metadata.role`;
- browser-supplied role/user ID;
- route/query role;
- stale cached client account state.

Admin account listings begin from S.A.G.A.-owned access rows. Do not treat the entire Supabase Auth directory as the S.A.G.A. product directory.

## Initial Admin APIs

Expected product APIs:

```text
GET    /api/admin/invitations
POST   /api/admin/invitations
DELETE /api/admin/invitations/[invitationId]

GET    /api/admin/accounts
PATCH  /api/admin/accounts/[userId]
```

Possible future admin APIs require separate need/contract; do not create a generic privileged RPC surface.

### Invitation create request

Conceptual input:

```json
{
  "email": "person@example.com",
  "role": "member"
}
```

Server normalizes/validates; browser does not send inviter ID or status.

### Account patch request

Only allow bounded fields such as:

```json
{
  "role": "member|admin",
  "status": "active|suspended"
}
```

Implementation should guard against accidental self-lockout/last-active-admin removal where relevant.

## First Admin Bootstrap

An invite-only product has a bootstrap problem before any app admin exists.

Initial S.A.G.A. owner/admin bootstrap is an explicit operator action for the new S.A.G.A. Supabase project, not public signup.

Acceptable bounded approach:

1. create/invite the owner identity through Supabase's trusted operator/Admin path;
2. obtain the exact verified Auth UUID;
3. create the first `saga_account_access` row as active admin through trusted SQL/service-role/operator tooling;
4. after that, ordinary invitations are created through the S.A.G.A. admin product flow.

Do not hardcode an email or UUID in migrations.

## RLS / Database Privilege Direction

For access/invitation tables:

- enable RLS;
- revoke broad browser mutation grants;
- use explicit policies only for safe self-readable state if the UI truly needs it;
- privileged claim/admin operations run server-side with tightly scoped service-role/database routines;
- privileged database routines use explicit safe search paths and do not grant execution to anon/authenticated unless intentionally needed;
- server operations return bounded product records rather than arbitrary table/query access.

The exact SQL is implemented in Phase 1B and tested before application to the hosted project.

## Secret Boundary

Never expose to browser/client bundle:

- Supabase service-role key;
- Supabase Auth Admin capability;
- B2 master key;
- B2 scoped application secret except inside server storage infrastructure;
- SMTP/provider secret;
- raw invitation/recovery token/hash except the browser/server confirmation values required by the supported Auth flow;
- database credentials.

Repository `.env.example` may document variable **names** only.

## Email Delivery Architecture

The application-level invitation flow is not the same as verified email deliverability.

Hosted readiness requires:

- correct Supabase Site URL;
- explicit redirect allowlist for S.A.G.A. origins;
- invite/recovery templates pointing to the S.A.G.A. confirmation endpoint using supported variables;
- production-capable custom SMTP or equivalent Supabase Auth email hook;
- authenticated sender domain (SPF/DKIM/etc. as required by the chosen mail system);
- rate limits suitable for the bounded demo;
- tested inbox delivery.

The exact SMTP/email provider is currently open. Do not couple application code to one provider unless a later decision selects it.

## Anti-Enumeration / Privacy

- no public account directory;
- no public invitation-status lookup by email;
- sign-in/recovery messages should avoid unnecessary account existence disclosure;
- foreign/missing account IDs on admin/product APIs fail according to bounded authorized semantics;
- admin-specific operational detail is acceptable only after active-admin authorization;
- logs must not record password/token values or full provider secret payloads.

## Audit Direction

Phase 1 requires enough metadata to answer who invited/accepted/changed access and when. A separate general audit-log subsystem is optional unless implementation evidence shows it is needed immediately.

At minimum preserve inviter/acceptance/revocation/update timestamps and authenticated actor IDs for privileged account changes where practical.

## Testing Contract

Deterministic tests should cover at least:

- no public signup route/action;
- anonymous private denial;
- valid Auth identity without S.A.G.A. access denied;
- active member allowed private product but denied admin;
- active admin allowed admin;
- suspended account denied private/admin;
- role not taken from user metadata/browser input;
- normalized invitation uniqueness/conflict behavior;
- email mismatch claim denied;
- revoked/expired/already-accepted claim denied;
- concurrent/double claim is safe;
- invitation record contains no raw token field/value;
- hostile redirect rejected;
- service-role/Admin secret not imported by client modules;
- account patch self/last-admin safety when implemented.

Hosted integration tests later cover:

- one real invitation email delivery;
- invite click/confirmation;
- password setup;
- later sign-in;
- session revocation/current-user behavior;
- admin revocation/suspension effects.

## Operational State Labels

Use precise language:

- **Implemented** — code/schema exists;
- **Validated** — deterministic tests or hosted verification for the specific claim passed;
- **Email delivery configured** — hosted SMTP/templates/redirects set;
- **Invitation E2E validated** — a real bounded invite was delivered and accepted;
- **Proposed** — documented only.

Do not call the invite system end-to-end complete merely because an API route and table exist.

## RenderLab Reference Disclaimer

RenderLab demonstrated useful separation between Supabase identity, product access, invitation state, fresh admin authorization and hosted email configuration. S.A.G.A. adopts those security principles because they fit this closed-demo requirement, but all names, schema, code, routes, resources and final behavior here belong to S.A.G.A.