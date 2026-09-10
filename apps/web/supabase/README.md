# S.A.G.A. v2 Supabase

This directory owns the **new v2 web application's** Supabase schema. It does not reuse the legacy v1 migration ownership and it does not use RenderLab tables.

## Phase-1 migration

`migrations/0001_closed_demo_access.sql` creates only the closed-demo admission foundation:

- `saga_account_access`
- `saga_invitations`
- privileged `saga_claim_invitation(...)`

Raw access/invitation tables have RLS enabled and browser grants revoked. Normal browser code must never use service-role credentials.

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

## Email delivery

The application records the S.A.G.A. invitation first, then requests email delivery through Supabase Auth Admin.

Before production/demo invitations are relied upon, verify in the S.A.G.A. Supabase project:

- Site URL;
- redirect allowlist including `/auth/confirm` on the real app origin;
- invitation template/link contract;
- recovery template if recovery is later enabled;
- production-capable custom SMTP or equivalent email hook;
- sender-domain authentication and practical rate limits.

Code success does not prove recipient delivery.
