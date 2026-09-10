# S.A.G.A. v2 Supabase

This directory owns the **new v2 web application's** Supabase schema. It does not reuse the legacy v1 migration ownership and it does not use RenderLab tables.

## Phase-1 migration

`migrations/0001_closed_demo_access.sql` creates only the closed-demo admission foundation:

- `saga_account_access`
- `saga_invitations`
- privileged `saga_claim_invitation(...)`
- privileged `saga_admin_set_account_access(...)`

Raw access/invitation tables have RLS enabled and browser grants revoked. Browser code uses only the project's publishable key. Privileged server code uses a current Supabase `sb_secret_...` key through `SUPABASE_SECRET_KEY`; never place that secret in a `NEXT_PUBLIC_*` variable or client bundle.

The database role used by Supabase secret keys is still `service_role`, so SQL grants in the migration intentionally target `service_role` even though application configuration uses the newer secret-key format rather than the legacy `service_role` JWT key.

## First-admin bootstrap

A brand-new project has no S.A.G.A. admin yet. Do not solve this by scanning/backfilling every Supabase Auth user or by trusting email/user metadata at runtime.

After the S.A.G.A.-owned Supabase project is created and migration `0001` is applied:

1. create or invite the intended operator identity through the Supabase Auth admin/dashboard boundary;
2. obtain that exact `auth.users.id`;
3. in the trusted SQL/admin boundary insert one explicit row:

```sql
insert into public.saga_account_access (user_id, role, status)
values ('<exact-auth-user-uuid>', 'admin', 'active');
```

That out-of-band bootstrap is the only initial bypass. Subsequent product access should be invitation-driven and server-authorized.

## API-key contract

For a new hosted S.A.G.A. Supabase project, use the current key model:

- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` -> `sb_publishable_...`, browser-safe only when RLS/policies protect exposed data;
- `SUPABASE_SECRET_KEY` -> `sb_secret_...`, server-only elevated key that bypasses RLS;
- `NEXT_PUBLIC_SUPABASE_URL` / `SUPABASE_URL` -> project URL.

Do not introduce the legacy `SUPABASE_SERVICE_ROLE_KEY` into the new v2 deployment unless a documented compatibility blocker forces a temporary fallback.

## Invitation email delivery

The application records the S.A.G.A. invitation first, then requests delivery through Supabase Auth Admin with `redirectTo` set to the trusted canonical URL:

```text
https://<saga-origin>/auth/confirm
```

`SAGA_PUBLIC_APP_URL` is required by the admin invitation endpoint. Production invitation URLs are never derived from the incoming request `Host`/origin.

### Hosted invite template contract

The SSR confirmation endpoint expects a token hash. Configure the hosted **Invite user** email template so the action URL reaches the exact `redirectTo` supplied by S.A.G.A. and adds the token hash/type:

```html
<a href="{{ .RedirectTo }}?token_hash={{ .TokenHash }}&type=invite">
  Accept S.A.G.A. invitation
</a>
```

Do not rely on a default flow that returns the authenticated session only in a URL fragment; server-side route handlers cannot read browser fragments. If the template contract changes, change `/auth/confirm` and this document together.

Before demo invitations are relied upon, verify in the S.A.G.A. Supabase project:

- Site URL points at the canonical S.A.G.A. deployment;
- redirect allowlist includes the exact `/auth/confirm` URL and only justified local/preview entries;
- Invite user template matches the token-hash contract above;
- recovery/password templates are configured before recovery is exposed;
- production-capable custom SMTP or an equivalent Auth email hook/provider is configured;
- sender domain authentication and practical delivery/rate limits are verified;
- provider email tracking/link rewriting is disabled for authentication mail;
- invitation behavior is tested with providers/security gateways that prefetch links, because URL prefetch can consume one-time Auth links.

Supabase accepting an invitation request is not proof that the recipient received the message. S.A.G.A. UI/API language must preserve that distinction.
