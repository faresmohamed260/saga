# S.A.G.A. v2 Phase 1E — Hosted Supabase Foundation Validation

**Date:** 2026-09-11

## Scope

This record covers only the dedicated hosted Supabase project creation and application of the active S.A.G.A. v2 database lineage. It does **not** claim hosted Auth redirect/template configuration, SMTP/email delivery, real invitation acceptance, runtime service-role deployment wiring, or Phase 1 completion.

## Explicit Owner Authorization

The owner explicitly approved:

- organization: **Fares Home Lab**;
- organization id: `imbicfntoeaqubhdcnpe`;
- a **new dedicated S.A.G.A. project** rather than reusing the existing `AI Studio` project;
- region: **Frankfurt / `eu-central-1`**;
- quoted Supabase project cost: **$0/month**.

The existing `AI Studio` project was not reused or modified.

## Created Hosted Project

- project name: `S.A.G.A.`
- project ref/id: `scmeqnpmhomzcwecjdtu`
- organization: `Fares Home Lab`
- region: `eu-central-1`
- status after creation: `ACTIVE_HEALTHY`
- API URL: `https://scmeqnpmhomzcwecjdtu.supabase.co`

A modern publishable key exists for the project, but no API key or secret value is stored in this validation document or committed to the repository.

## Applied Active v2 Migration Lineage

The new project began with no application migrations recorded.

The exact active repository lineage from `apps/web/supabase/migrations/` was applied in order:

1. `20260911142000_closed_demo_account_access.sql`
2. `20260911173500_admin_operations.sql`
3. `20260911174500_admin_operation_hardening.sql`

All three hosted migration applications returned success.

Supabase then reported the following hosted migration history:

- `20260911150526` — `closed_demo_account_access`
- `20260911150550` — `admin_operations`
- `20260911150557` — `admin_operation_hardening`

The Supabase-managed hosted migration timestamps differ from repository filename timestamps; the ordering and migration names match the active repository lineage.

## Hosted Security Advisor Review

Supabase security advisors reported only two informational `rls_enabled_no_policy` findings:

- `public.saga_account_access`
- `public.saga_invitations`

These are expected for the current closed-demo authorization design. Both tables deliberately enable and force RLS while browser-role table privileges are revoked; privileged server services use the service-role boundary rather than browser RLS policies.

No blocking hosted security advisor finding was reported.

Reference: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy

## Hosted Performance Advisor Review

Supabase performance advisors reported informational findings only:

- missing covering indexes for four foreign-key columns:
  - `saga_account_access.invited_by`
  - `saga_account_access.updated_by`
  - `saga_invitations.accepted_by`
  - `saga_invitations.invited_by`
- `saga_invitations_status_invited_at_idx` currently unused on the newly created empty project.

These do not block Phase 1 hosted functional proof. Index tuning should be based on actual query/data behavior rather than adding indexes solely to silence new-project advisory noise.

References:

- https://supabase.com/docs/guides/database/database-linter?lint=0001_unindexed_foreign_keys
- https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index

## Preserved Boundaries

- `AI Studio` remains separate and unmodified.
- RenderLab/Studio resources remain separate and unmodified.
- No service-role secret was exposed or committed.
- No SMTP credentials or sender-domain settings were invented.
- No hosted invitation-delivery claim was made.
- No real user/admin was silently bootstrapped through an unapproved identity path.
- No Vercel project was repurposed.

## Remaining Phase 1 Hosted Gate

Before Phase 1 can close, the following still require real hosted proof:

1. configure the S.A.G.A. Auth Site URL and redirect allowlist;
2. configure supported invite/recovery templates;
3. configure production-capable SMTP or an equivalent Auth email hook with authenticated sender identity;
4. wire deployed application server secrets/config to this dedicated Supabase project without exposing privileged credentials;
5. establish the first trusted S.A.G.A. admin through an explicit operator/bootstrap path;
6. deliver at least one real invitation to an inbox;
7. complete confirmation -> invitation claim -> password setup -> private application access;
8. prove later sign-in works;
9. prove hosted suspension/revocation fails closed as designed;
10. update durable validation and only then close Phase 1.

## Conclusion

The dedicated hosted S.A.G.A. Supabase project now exists and the active v2 database schema is applied and advisor-reviewed. The **hosted database foundation is complete**, but **hosted Auth/email/end-to-end invitation proof remains pending**.